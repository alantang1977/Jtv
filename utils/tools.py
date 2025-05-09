import datetime
import json
import logging
import os
import re
import shutil
import sys
from collections import defaultdict
from logging.handlers import RotatingFileHandler
from time import time

import pytz
import requests
from bs4 import BeautifulSoup
from flask import send_file, make_response
from opencc import OpenCC

import utils.constants as constants
from utils.config import config
from utils.types import ChannelData

opencc_t2s = OpenCC("t2s")

def get_logger(path, level=logging.ERROR, init=False):
    """获取日志记录器"""
    logger = logging.getLogger(path)
    logger.setLevel(level)
    
    if not logger.handlers or init:
        # 清除已有处理器
        if logger.handlers:
            logger.handlers = []
            
        # 创建文件处理器
        file_handler = RotatingFileHandler(
            path, maxBytes=1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(level)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        # 创建格式化器并添加到处理器
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 添加处理器到logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger

def format_interval(t):
    """将秒数格式化为时钟时间 [H:]MM:SS"""
    minutes, seconds = divmod(int(t), 60)
    hours, minutes = divmod(minutes, 60)
    
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"

def get_pbar_remaining(n=0, total=0, start_time=None):
    """获取进度条剩余时间"""
    if n == 0 or start_time is None:
        return "??:??"
    
    elapsed = time() - start_time
    if n >= total:
        return format_interval(elapsed)
    
    rate = n / elapsed
    remaining = (total - n) / rate
    return format_interval(remaining)

def update_file(final_file, old_file, copy=False):
    """更新文件"""
    old_file_path = resource_path(old_file, persistent=True)
    final_file_path = resource_path(final_file, persistent=True)
    
    if os.path.exists(old_file_path):
        if copy:
            shutil.copyfile(old_file_path, final_file_path)
        else:
            os.replace(old_file_path, final_file_path)

def filter_by_date(data):
    """按日期过滤数据"""
    if not config.open_history:
        return data
    
    recent_days = config.recent_days
    if recent_days <= 0:
        return data
    
    today = datetime.datetime.now()
    filtered_data = []
    
    for item in data:
        if 'date' in item:
            try:
                item_date = datetime.datetime.strptime(item['date'], '%Y-%m-%d')
                if (today - item_date).days <= recent_days:
                    filtered_data.append(item)
            except ValueError:
                filtered_data.append(item)
        else:
            filtered_data.append(item)
    
    return filtered_data

def get_soup(source):
    """从源获取BeautifulSoup对象"""
    try:
        if source.startswith('http'):
            response = requests.get(source, timeout=config.request_timeout)
            response.raise_for_status()
            return BeautifulSoup(response.text, 'html.parser')
        else:
            if os.path.exists(source):
                with open(source, 'r', encoding='utf-8') as f:
                    return BeautifulSoup(f.read(), 'html.parser')
    except Exception as e:
        print(f"Error getting soup: {e}")
        return None

def get_resolution_value(resolution_str):
    """从分辨率字符串获取数值表示"""
    match = re.match(r'(\d+)x(\d+)', resolution_str)
    if match:
        width = int(match.group(1))
        height = int(match.group(2))
        return width * height
    return 0

def get_total_urls(info_list: list[ChannelData], ipv_type_prefer, origin_type_prefer, rtmp_type=None) -> list:
    """从信息列表获取全部URL"""
    # 按IP类型和来源类型偏好排序
    sorted_urls = []
    
    for info in info_list:
        if rtmp_type and not info.url.startswith(rtmp_type):
            continue
            
        # 检查IP类型匹配
        if not check_ipv_type_match(info.ipv_type):
            continue
            
        # 应用偏好排序
        ip_weight = ipv_type_prefer.index(info.ipv_type) if info.ipv_type in ipv_type_prefer else len(ipv_type_prefer)
        origin_weight = origin_type_prefer.index(info.origin) if info.origin in origin_type_prefer else len(origin_type_prefer)
        
        # 添加到排序列表
        sorted_urls.append((info, ip_weight + origin_weight))
    
    # 按权重排序
    sorted_urls.sort(key=lambda x: x[1])
    
    # 只返回URL信息
    return [item[0] for item in sorted_urls]

def get_total_urls_from_sorted_data(data):
    """从排序数据获取全部URL，带日期过滤和去重"""
    filtered_data = filter_by_date(data)
    urls = []
    seen = set()
    
    for item in filtered_data:
        if 'urls' in item:
            for url_info in item['urls']:
                url = url_info.get('url', '')
                if url and url not in seen:
                    seen.add(url)
                    urls.append(url_info)
    
    return urls

def check_ipv6_support():
    """检查系统网络是否支持IPv6"""
    try:
        import socket
        # 创建IPv6套接字并尝试连接到IPv6地址
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.settimeout(1)
        sock.connect(("2001:4860:4860::8888", 53))
        sock.close()
        return True
    except:
        return False

def check_ipv_type_match(ipv_type: str) -> bool:
    """检查IP类型是否匹配配置"""
    config_ipv = config.ipv_type
    
    if "all" in config_ipv or "全部" in config_ipv:
        return True
    
    if "ipv4" in config_ipv and ipv_type == "ipv4":
        return True
    
    if "ipv6" in config_ipv and ipv_type == "ipv6":
        return True
    
    return False

def check_url_by_keywords(url, keywords=None):
    """通过URL关键字检查"""
    if not keywords:
        return True
    
    for keyword in keywords:
        if keyword in url:
            return True
    
    return False

def merge_objects(*objects, match_key=None):
    """
    合并对象
    
    Args:
        *objects: 要合并的字典
        match_key: 如果dict1[key]是字典列表，将使用此键匹配并合并字典
    """
    result = {}
    
    for obj in objects:
        if not isinstance(obj, dict):
            continue
            
        for key, value in obj.items():
            if key not in result:
                result[key] = value
            else:
                # 处理嵌套字典
                if isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = merge_objects(result[key], value)
                # 处理列表
                elif isinstance(result[key], list) and isinstance(value, list):
                    if match_key:
                        # 按match_key合并列表中的字典
                        merged_list = result[key].copy()
                        for item in value:
                            if isinstance(item, dict) and match_key in item:
                                # 查找匹配项
                                found = False
                                for i, existing in enumerate(merged_list):
                                    if isinstance(existing, dict) and match_key in existing and existing[match_key] == item[match_key]:
                                        merged_list[i] = merge_objects(existing, item)
                                        found = True
                                        break
                                if not found:
                                    merged_list.append(item)
                            else:
                                merged_list.append(item)
                        result[key] = merged_list
                    else:
                        # 简单合并列表
                        result[key].extend(value)
                else:
                    # 其他情况，用新值覆盖
                    result[key] = value
                    
    return result

def get_ip_address():
    """获取IP地址"""
    try:
        response = requests.get('https://api.ipify.org?format=json', timeout=5)
        if response.status_code == 200:
            return response.json().get('ip', 'unknown')
    except:
        pass
    return 'unknown'

def get_epg_url():
    """获取EPG结果URL"""
    if config.open_epg:
        return f"{config.app_host}:{config.app_port}/epg"
    return ""

def convert_to_m3u(path=None, first_channel_name=None, data=None):
    """将结果txt转换为m3u格式"""
    if not data and path:
        data = get_result_file_content(path, show_content=True)
    
    if not data:
        return ""
    
    m3u_content = "#EXTM3U\n"
    
    if first_channel_name:
        m3u_content += f"#EXTINF:-1,{first_channel_name}\n"
    
    for line in data.splitlines():
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('#EXTINF:'):
            m3u_content += line + '\n'
        else:
            # 检查是否是URL
            if line.startswith(('http', 'rtmp', 'rtsp')):
                m3u_content += line + '\n'
    
    return m3u_content

def get_result_file_content(path=None, show_content=False, file_type=None):
    """获取结果文件内容"""
    if not path:
        path = config.final_file
    
    file_path = resource_path(path, persistent=True)
    
    if not os.path.exists(file_path):
        return ""
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            if file_type == 'm3u' and not content.startswith('#EXTM3U'):
                content = convert_to_m3u(data=content)
            
            if show_content:
                return content
            
            return f"File size: {os.path.getsize(file_path)} bytes"
    except Exception as e:
        print(f"Error reading file: {e}")
        return ""

def remove_duplicates_from_list(data_list, seen, filter_host=False, ipv6_support=True):
    """从数据列表中移除重复项"""
    result = []
    
    for item in data_list:
        if isinstance(item, dict):
            url = item.get('url', '')
            if not url:
                continue
                
            # 检查主机过滤
            if filter_host:
                host = get_url_host(url)
                if host in seen:
                    continue
                seen.add(host)
            else:
                if url in seen:
                    continue
                seen.add(url)
                
            # 检查IPv6支持
            if not ipv6_support and url.startswith('http://['):
                continue
                
            result.append(item)
        else:
            if item not in seen:
                seen.add(item)
                result.append(item)
    
    return result

def process_nested_dict(data, seen, filter_host=False, ipv6_support=True):
    """处理嵌套字典"""
    if isinstance(data, dict):
        result = {}
        for key, value in data.items():
            if isinstance(value, list):
                result[key] = remove_duplicates_from_list(
                    value, seen, filter_host=filter_host, ipv6_support=ipv6_support
                )
            elif isinstance(value, dict):
                result[key] = process_nested_dict(value, seen, filter_host=filter_host, ipv6_support=ipv6_support)
            else:
                result[key] = value
        return result
    elif isinstance(data, list):
        return remove_duplicates_from_list(
            data, seen, filter_host=filter_host, ipv6_support=ipv6_support
        )
    else:
        return data

def get_url_host(url):
    """获取URL的主机部分"""
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc
    except:
        return url

def add_url_info(url, info):
    """向URL添加信息"""
    if not info:
        return url
        
    return f"{url}#{info}"

def format_url_with_cache(url, cache=None):
    """格式化URL带缓存信息"""
    if not cache:
        return url
        
    cache_str = json.dumps(cache)
    return f"{url}?cache={cache_str}"

def remove_cache_info(string):
    """从字符串中移除缓存信息"""
    return re.sub(r'\?cache={[^}]*}', '', string)

def resource_path(relative_path, persistent=False):
    """获取资源路径"""
    if hasattr(sys, '_MEIPASS'):
        # 处理PyInstaller打包后的情况
        return os.path.join(sys._MEIPASS, relative_path)
    
    if persistent:
        # 持久化路径，用于用户数据
        home_dir = os.path.expanduser("~")
        app_dir = os.path.join(home_dir, ".iptv-api")
        return os.path.join(app_dir, relative_path)
    
    # 开发环境路径
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, '..', relative_path)

def write_content_into_txt(content, path=None, position=None, callback=None):
    """将内容写入txt文件"""
    if not path:
        path = config.final_file
    
    file_path = resource_path(path, persistent=True)
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        
        if position == 'top':
            # 在文件顶部添加内容
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    old_content = f.read()
                content = content + '\n' + old_content
                
        elif position == 'bottom':
            # 在文件底部添加内容
            if os.path.exists(file_path):
                with open(file_path, 'a', encoding='utf-8') as f:
                    f.write('\n' + content)
                return
        
        # 覆盖写入
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
            
        if callback:
            callback()
            
        return True
    except Exception as e:
        print(f"Error writing file: {e}")
        return False

def format_name(name: str) -> str:
    """格式化名称，带替换和小写处理"""
    # 替换特殊字符
    name = re.sub(r'[<>:"/\\|?*]', '_', name)
    # 转换为小写
    name = name.lower()
    return name

def get_headers_key_value(content: str) -> dict:
    """从内容获取请求头键值对"""
    headers = {}
    if not content:
        return headers
        
    lines = content.splitlines()
    for line in lines:
        line = line.strip()
        if not line or ':' not in line:
            continue
            
        key, value = line.split(':', 1)
        headers[key.strip()] = value.strip()
    
    return headers

def get_name_url(content, pattern, open_headers=False, check_url=True):
    """
    使用正则表达式从内容中提取名称和URL
    
    :param content: str, 要搜索的输入内容
    :param pattern: re.Pattern, 编译后的正则表达式模式
    :param open_headers: bool, 是否提取请求头
    :param check_url: bool, 是否验证URL存在
    """
    match = pattern.search(content)
    if not match:
        return None, None, None
    
    name = match.group(1).strip() if match.group(1) else ""
    url = match.group(2).strip() if match.group(2) else ""
    
    headers = None
    if open_headers and match.group(3):
        headers = get_headers_key_value(match.group(3))
    
    if check_url and not url:
        return None, None, None
    
    return name, url, headers

def get_real_path(path) -> str:
    """获取真实路径"""
    return os.path.realpath(resource_path(path))

def get_urls_from_file(path: str, pattern_search: bool = True) -> list:
    """从文件获取URL列表"""
    file_path = resource_path(path)
    urls = []
    
    if not os.path.exists(file_path):
        return urls
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            if pattern_search:
                # 使用正则表达式匹配URL
                url_pattern = re.compile(r'(https?|rtmp|rtsp)://\S+')
                urls = url_pattern.findall(content)
            else:
                # 逐行解析
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith(('http', 'rtmp', 'rtsp')):
                        urls.append(line)
                        
    except Exception as e:
        print(f"Error reading file: {e}")
    
    return urls

def get_name_urls_from_file(path: str, format_name_flag: bool = False) -> dict[str, list]:
    """从文件获取名称和URLs"""
    file_path = resource_path(path)
    result = defaultdict(list)
    
    if not os.path.exists(file_path):
        return result
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
            # 匹配 #EXTINF 格式的M3U文件
            extinf_pattern = re.compile(r'#EXTINF:-?\d*,(.*?)\n(.*?)(?:\n|$)')
            matches = extinf_pattern.findall(content)
            
            for name, url in matches:
                name = name.strip()
                url = url.strip()
                
                if format_name_flag:
                    name = format_name(name)
                    
                result[name].append(url)
                
    except Exception as e:
        print(f"Error reading file: {e}")
    
    return result

def get_name_uri_from_dir(path: str) -> dict:
    """从目录获取名称和URI（仅从文件名）"""
    dir_path = resource_path(path)
    result = {}
    
    if not os.path.exists(dir_path) or not os.path.isdir(dir_path):
        return result
    
    try:
        for filename in os.listdir(dir_path):
            file_path = os.path.join(dir_path, filename)
            if os.path.isfile(file_path):
                name, _ = os.path.splitext(filename)
                result[name] = filename
                
    except Exception as e:
        print(f"Error reading directory: {e}")
    
    return result

def get_datetime_now():
    """获取当前日期时间"""
    tz = pytz.timezone(config.time_zone)
    return datetime.datetime.now(tz)

def get_version_info():
    """获取版本信息"""
    try:
        with open(resource_path('VERSION'), 'r') as f:
            return f.read().strip()
    except:
        return "Unknown"

def join_url(url1: str, url2: str) -> str:
    """拼接URL"""
    from urllib.parse import urljoin
    return urljoin(url1, url2)

def find_by_id(data: dict, id: int) -> dict:
    """通过ID查找嵌套字典"""
    if isinstance(data, dict):
        if 'id' in data and data['id'] == id:
            return data
        for value in data.values():
            result = find_by_id(value, id)
            if result:
                return result
    elif isinstance(data, list):
        for item in data:
            result = find_by_id(item, id)
            if result:
                return result
    return None

def custom_print(*args, **kwargs):
    """自定义打印函数"""
    # 这里可以添加日志记录等额外功能
    print(*args, **kwargs)

def get_urls_len(data) -> int:
    """获取字典中URLs的长度"""
    count = 0
    if isinstance(data, dict):
        for key, value in data.items():
            if key == 'urls' and isinstance(value, list):
                count += len(value)
            else:
                count += get_urls_len(value)
    elif isinstance(data, list):
        for item in data:
            count += get_urls_len(item)
    return count
