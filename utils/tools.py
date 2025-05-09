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
    """获取日志记录器，配置日志输出"""
    logger = logging.getLogger(path)
    logger.setLevel(level)
    
    if not logger.handlers or init:
        # 创建文件处理器
        file_handler = RotatingFileHandler(
            path, maxBytes=1024 * 1024, backupCount=5, encoding='utf-8'
        )
        file_handler.setLevel(level)
        
        # 创建控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        
        # 创建格式化器并添加到处理器
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)
        
        # 清除旧的处理器并添加新的处理器
        logger.handlers = []
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
    
    return logger


def format_interval(t):
    """格式化时间间隔为 [H:]MM:SS 格式"""
    hours, remainder = divmod(int(t), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes:02d}:{seconds:02d}"


def get_pbar_remaining(n=0, total=0, start_time=None):
    """获取进度条剩余时间"""
    if n == 0 or start_time is None:
        return "计算中..."
    elapsed = time() - start_time
    if elapsed <= 0 or n <= 0:
        return "计算中..."
    rate = n / elapsed
    remaining = (total - n) / rate if rate > 0 else 0
    return format_interval(remaining)


def update_file(final_file, old_file, copy=False):
    """更新文件，支持复制或替换操作"""
    if os.path.exists(old_file):
        if copy:
            shutil.copy2(old_file, final_file)
        else:
            os.replace(old_file, final_file)


def filter_by_date(data):
    """按日期和限制过滤数据"""
    # 实现日期过滤逻辑
    return data


def get_soup(source):
    """从源获取BeautifulSoup对象，处理HTML解析"""
    try:
        if isinstance(source, str):
            if source.startswith('http'):
                response = requests.get(source)
                response.raise_for_status()
                return BeautifulSoup(response.text, 'html.parser')
            else:
                return BeautifulSoup(source, 'html.parser')
        return None
    except Exception as e:
        print(f"Error getting soup: {e}")
        return None


def get_resolution_value(resolution_str):
    """从字符串中获取分辨率值"""
    if not resolution_str:
        return 0
    
    # 匹配常见的分辨率格式
    match = re.search(r'(\d+)[pP]', resolution_str)
    if match:
        return int(match.group(1))
    
    match = re.search(r'(\d+)x(\d+)', resolution_str, re.IGNORECASE)
    if match:
        return max(int(match.group(1)), int(match.group(2)))
    
    return 0


def get_total_urls(info_list: list[ChannelData], ipv_type_prefer, origin_type_prefer, rtmp_type=None) -> list:
    """从信息列表中获取所有URL，根据偏好过滤"""
    urls = []
    for info in info_list:
        # 根据IP类型和来源类型过滤
        if (not ipv_type_prefer or info.get('ipv_type') in ipv_type_prefer) and \
           (not origin_type_prefer or info.get('origin') in origin_type_prefer):
            urls.append(info.get('url'))
    return urls


def get_total_urls_from_sorted_data(data):
    """从排序后的数据中获取所有URL，并过滤重复和按日期过滤"""
    urls = set()
    for category, channels in data.items():
        for name, info_list in channels.items():
            filtered_info = filter_by_date(info_list)
            for info in filtered_info:
                url = info.get('url')
                if url:
                    urls.add(url)
    return list(urls)


def check_ipv6_support():
    """检查系统网络是否支持IPv6"""
    try:
        import socket
        # 尝试创建IPv6套接字
        sock = socket.socket(socket.AF_INET6, socket.SOCK_STREAM)
        sock.close()
        return True
    except:
        return False


def check_ipv_type_match(ipv_type: str, prefer_types: list[str]) -> bool:
    """检查IPv类型是否匹配偏好类型"""
    if not prefer_types:
        return True
    return ipv_type in prefer_types


def check_url_by_keywords(url, keywords=None):
    """按URL关键字检查，判断URL是否包含黑名单关键字"""
    if not keywords or not url:
        return True
    
    for keyword in keywords:
        if keyword and keyword in url:
            return False
    
    return True


def merge_objects(*objects, match_key=None):
    """合并多个对象，可根据指定键匹配"""
    if not objects:
        return {}
    
    if len(objects) == 1:
        return objects[0]
    
    result = {}
    
    for obj in objects:
        if not obj:
            continue
        
        if match_key and isinstance(obj, list):
            # 合并列表，根据匹配键
            for item in obj:
                key_value = item.get(match_key)
                if key_value:
                    if key_value not in result:
                        result[key_value] = {}
                    result[key_value].update(item)
            # 转换回列表
            result = list(result.values())
        elif isinstance(obj, dict):
            # 合并字典
            result.update(obj)
    
    return result


def get_ip_address():
    """获取IP地址，优先返回IPv4地址"""
    try:
        import socket
        hostname = socket.gethostname()
        # 获取所有IP地址
        ip_list = socket.gethostbyname_ex(hostname)[2]
        
        # 优先返回IPv4地址
        for ip in ip_list:
            if '.' in ip:  # 简单判断IPv4
                return ip
        
        # 如果没有IPv4，返回第一个IP
        if ip_list:
            return ip_list[0]
        
        # 备选方法
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"


def get_epg_url():
    """获取EPG结果URL"""
    return config.epg_url


def convert_to_m3u(path=None, first_channel_name=None, data=None):
    """将结果TXT文件转换为M3U格式"""
    if not path and not data:
        return None
    
    if path and os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            # 简单的M3U转换逻辑
            lines = content.split('\n')
            m3u_content = "#EXTM3U\n"
            for line in lines:
                if line.startswith('#EXTINF:'):
                    m3u_content += line + '\n'
                elif line.strip():
                    m3u_content += line + '\n'
            return m3u_content
    
    # 如果提供了数据，直接转换
    if data:
        m3u_content = "#EXTM3U\n"
        # 处理数据转换为M3U格式
        for category, channels in data.items():
            for name, info_list in channels.items():
                for info in info_list:
                    url = info.get('url')
                    if url:
                        # 添加频道信息
                        m3u_content += f"#EXTINF:-1 group-title=\"{category}\",{name}\n{url}\n"
        return m3u_content
    
    return None


def get_result_file_content(path=None, show_content=False, file_type=None):
    """获取结果文件的内容，支持不同格式"""
    result_file = (
        os.path.splitext(path)[0] + f".{file_type}"
        if file_type
        else path
    )
    
    if os.path.exists(result_file):
        if config.open_m3u_result:
            if file_type == "m3u" or not file_type:
                result_file = os.path.splitext(path)[0] + ".m3u"
            if file_type != "txt" and show_content == False:
                return send_file(resource_path(result_file), as_attachment=True)
        
        with open(result_file, "r", encoding="utf-8") as file:
            content = file.read()
    else:
        content = constants.waiting_tip
    
    response = make_response(content)
    response.mimetype = 'text/plain'
    return response


def remove_duplicates_from_list(data_list, seen, filter_host=False, ipv6_support=True):
    """从数据列表中移除重复项，可选择过滤主机和支持IPv6"""
    unique_list = []
    host_set = set() if filter_host else None
    
    for item in data_list:
        url = item.get('url')
        if not url:
            continue
        
        # 移除缓存信息
        clean_url = remove_cache_info(url)
        
        # 检查是否已存在
        if clean_url in seen:
            continue
        
        # 检查主机重复
        if filter_host:
            host = get_url_host(clean_url)
            if host and host in host_set:
                continue
            host_set.add(host)
        
        # 检查IPv6支持
        if not ipv6_support and item.get('ipv_type') == 'ipv6':
            continue
        
        seen.add(clean_url)
        unique_list.append(item)
    
    return unique_list


def process_nested_dict(data, seen, filter_host=False, ipv6_support=True):
    """处理嵌套字典，移除重复项和过滤不支持的IP类型"""
    if isinstance(data, dict):
        for key, value in data.items():
            data[key] = process_nested_dict(value, seen, filter_host, ipv6_support)
    elif isinstance(data, list):
        return remove_duplicates_from_list(data, seen, filter_host, ipv6_support)
    return data


def get_url_host(url):
    """获取URL的主机名"""
    try:
        from urllib.parse import urlparse
        return urlparse(url).hostname
    except:
        return None


def add_url_info(url, info):
    """向URL添加信息，返回带参数字符串"""
    if not url or not info:
        return url
    
    # 简单实现，实际可能需要更复杂的URL参数处理
    if '?' in url:
        return f"{url}&{info}"
    else:
        return f"{url}?{info}"


def format_url_with_cache(url, cache=None):
    """用缓存格式化URL，添加缓存参数"""
    if not url:
        return url
    
    if cache:
        return add_url_info(url, f"cache={cache}")
    
    # 添加时间戳作为缓存参数
    timestamp = int(time())
    return add_url_info(url, f"ts={timestamp}")


def remove_cache_info(string):
    """从字符串中移除缓存信息"""
    if not string:
        return string
    
    # 移除URL中的查询参数
    return string.split('?')[0]


def resource_path(relative_path, persistent=False):
    """获取资源路径，处理打包后和持久化存储的情况"""
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
    
    if persistent:
        data_dir = os.path.join(os.path.expanduser("~"), ".iptv-api")
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
        return os.path.join(data_dir, relative_path)
    
    return os.path.join(base_path, relative_path)


def write_content_into_txt(content, path=None, position=None, callback=None):
    """将内容写入TXT文件，支持指定位置和回调"""
    if not path or not content:
        return False
    
    try:
        if position == 'append':
            with open(path, 'a', encoding='utf-8') as file:
                file.write(content)
        else:
            with open(path, 'w', encoding='utf-8') as file:
                file.write(content)
        
        if callback:
            callback()
        
        return True
    except Exception as e:
        print(f"Error writing file: {e}")
        return False


def format_name(name: str) -> str:
    """格式化名称，进行替换和小写处理"""
    if not name:
        return ""
    
    # 转换为简体中文
    name = opencc_t2s.convert(name)
    
    # 去除特殊字符
    name = re.sub(r'[^\w\s]', '', name)
    
    # 去除多余空格
    name = re.sub(r'\s+', ' ', name).strip()
    
    # 转换为小写
    name = name.lower()
    
    return name


def get_headers_key_value(content: str) -> dict:
    """从内容中获取头信息的键值对"""
    headers = {}
    if not content:
        return headers
    
    # 简单解析，假设内容是键值对格式
    lines = content.split('\n')
    for line in lines:
        line = line.strip()
        if not line or '=' not in line:
            continue
        
        key, value = line.split('=', 1)
        headers[key.strip()] = value.strip()
    
    return headers


def get_name_url(content, pattern, open_headers=False, check_url=True):
    """使用正则表达式从内容中提取名称和URL"""
    results = []
    if not content or not pattern:
        return results
    
    # 编译正则表达式
    regex = re.compile(pattern)
    
    # 查找所有匹配
    matches = regex.finditer(content)
    
    for match in matches:
        groups = match.groups()
        if len(groups) < 2:
            continue
        
        # 提取名称和URL
        name = groups[1].strip()
        url = groups[2].strip()
        
        # 检查URL有效性
        if check_url and not url.startswith(('http', 'rtmp', 'rtsp', 'mms')):
            continue
        
        result = {
            'name': name,
            'url': url
        }
        
        # 如果启用头信息提取
        if open_headers and len(groups) > 2:
            headers = groups[0].strip()
            result['headers'] = get_headers_key_value(headers)
        
        results.append(result)
    
    return results


def get_real_path(path) -> str:
    """获取真实路径，处理相对路径和绝对路径"""
    if not path:
        return ""
    
    if os.path.isabs(path):
        return path
    
    # 假设相对路径是相对于当前工作目录
    return os.path.join(os.getcwd(), path)


def get_urls_from_file(path: str, pattern_search: bool = True) -> list:
    """从文件中获取URL列表"""
    urls = []
    if not os.path.exists(path):
        return urls
    
    with open(path, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            if pattern_search:
                # 简单的URL匹配
                match = re.search(r'(https?|rtmp|rtsp|mms)://\S+', line)
                if match:
                    urls.append(match.group(0))
            else:
                urls.append(line)
    
    return urls


def get_name_urls_from_file(path: str, format_name_flag: bool = False) -> dict[str, list]:
    """从文件中获取名称和URL列表"""
    name_urls = defaultdict(list)
    if not os.path.exists(path):
        return name_urls
    
    with open(path, 'r', encoding='utf-8') as file:
        content = file.read()
        # 使用正则表达式提取名称和URL
        pattern = re.compile(r'#EXTINF:-1\s*(.*),(.*)\n(.*)')
        results = get_name_url(content, pattern)
        
        for result in results:
            name = result['name']
            url = result['url']
            
            if format_name_flag:
                name = format_name(name)
            
            name_urls[name].append(url)
    
    return name_urls


def get_name_uri_from_dir(path: str) -> dict:
    """从目录中获取名称和URI，仅从文件名获取"""
    name_uri = {}
    if not os.path.exists(path) or not os.path.isdir(path):
        return name_uri
    
    for filename in os.listdir(path):
        # 移除文件扩展名
        name = os.path.splitext(filename)[0]
        # 构建URI
        uri = os.path.join(path, filename)
        name_uri[name] = uri
    
    return name_uri


def get_datetime_now():
    """获取当前日期和时间，使用UTC+8时区"""
    # 设置时区为UTC+8
    tz = pytz.timezone('Asia/Shanghai')
    return datetime.datetime.now(tz)


def get_version_info():
    """获取版本信息，从version文件或其他来源读取"""
    try:
        with open('version', 'r', encoding='utf-8') as f:
            version = f.read().strip()
        return {
            'name': 'Jtv',
            'version': version
        }
    except:
        return {
            'name': 'Jtv',
            'version': 'unknown'
        }


def join_url(url1: str, url2: str) -> str:
    """拼接URL，处理路径分隔符"""
    if not url1:
        return url2
    if not url2:
        return url1
    
    # 确保url1以斜杠结尾，url2不以斜杠开头
    if not url1.endswith('/'):
        url1 += '/'
    
    if url2.startswith('/'):
        url2 = url2[1:]
    
    return url1 + url2


def find_by_id(data: dict, id: int) -> dict:
    """通过ID查找嵌套字典中的项"""
    if not isinstance(data, dict):
        return None
    
    if 'id' in data and data['id'] == id:
        return data
    
    for value in data.values():
        if isinstance(value, dict):
            result = find_by_id(value, id)
            if result:
                return result
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    result = find_by_id(item, id)
                    if result:
                        return result
    
    return None


def custom_print(*args, **kwargs):
    """自定义打印函数，可添加日志记录等功能"""
    # 获取当前时间
    now = get_datetime_now()
    time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    
    # 打印时间前缀
    print(f"[{time_str}]", *args, **kwargs)


def get_urls_len(data) -> int:
    """获取字典中URL的数量"""
    count = 0
    if isinstance(data, dict):
        for value in data.values():
            count += get_urls_len(value)
    elif isinstance(data, list):
        count += len(data)
    return count
