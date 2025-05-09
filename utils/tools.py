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
from utils.config import config, resource_path
from utils.types import ChannelData

opencc_t2s = OpenCC("t2s")


def get_logger(path, level=logging.ERROR, init=False):
    """
    获取日志记录器
    """
    logger = logging.getLogger(__name__)
    logger.setLevel(level)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    if init:
        file_handler = RotatingFileHandler(path, maxBytes=1024 * 1024, backupCount=5)
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    return logger


def format_interval(t):
    """
    格式化时间间隔为 [H:]MM:SS 格式
    """
    m, s = divmod(int(t), 60)
    h, m = divmod(m, 60)
    if h:
        return f"{h}:{m:02d}:{s:02d}"
    else:
        return f"{m:02d}:{s:02d}"


def get_pbar_remaining(n=0, total=0, start_time=None):
    """
    获取进度条剩余时间
    """
    if n == 0 or start_time is None:
        return "未知"
    elapsed_time = time() - start_time
    if n < total:
        remaining_time = elapsed_time * (total - n) / n
        return format_interval(remaining_time)
    return "0:00"


def update_file(final_file, old_file, copy=False):
    """
    更新文件
    """
    if os.path.exists(old_file):
        if copy:
            shutil.copy2(old_file, final_file)
        else:
            os.replace(old_file, final_file)


def filter_by_date(data):
    """
    按日期和限制过滤数据
    """
    # 实现过滤逻辑
    return data


def get_soup(source):
    """
    从源获取BeautifulSoup对象
    """
    try:
        response = requests.get(source)
        response.raise_for_status()
        return BeautifulSoup(response.text, 'html.parser')
    except requests.RequestException as e:
        print(f"请求出错: {e}")
        return None


def get_resolution_value(resolution_str):
    """
    从字符串中获取分辨率值
    """
    match = re.search(r'(\d+)x(\d+)', resolution_str)
    if match:
        width, height = map(int, match.groups())
        return width * height
    return 0


def get_total_urls(info_list: list[ChannelData], ipv_type_prefer, origin_type_prefer, rtmp_type=None) -> list:
    """
    从信息列表中获取所有URL
    """
    urls = []
    for info in info_list:
        if rtmp_type and info.get('rtmp_type') != rtmp_type:
            continue
        if check_ipv_type_match(info.get('ipv_type', ''), ipv_type_prefer):
            if origin_type_prefer is None or info.get('origin') in origin_type_prefer:
                urls.append(info['url'])
    return urls


def get_total_urls_from_sorted_data(data):
    """
    从排序后的数据中获取所有URL，并过滤重复和按日期过滤
    """
    urls = []
    for category in data.values():
        for channel in category.values():
            for info in channel:
                url = info['url']
                if url not in urls:
                    urls.append(url)
    return filter_by_date(urls)


def check_ipv6_support():
    """
    检查系统网络是否支持IPv6
    """
    import socket
    try:
        socket.create_connection(("2001:4860:4860::8888", 53), timeout=1)
        return True
    except OSError:
        return False


def check_ipv_type_match(ipv_type: str, prefer_types: list[str]) -> bool:
    """
    检查IPv类型是否匹配
    """
    return not prefer_types or ipv_type in prefer_types


def check_url_by_keywords(url, keywords=None):
    """
    按URL关键字检查
    """
    if keywords:
        for keyword in keywords:
            if keyword in url:
                return True
    return False


def merge_objects(*objects, match_key=None):
    """
    合并对象
    """
    result = {}
    for obj in objects:
        if isinstance(obj, dict):
            for key, value in obj.items():
                if match_key and isinstance(value, list):
                    if key not in result:
                        result[key] = []
                    existing = {item[match_key]: item for item in result[key]}
                    for item in value:
                        if item[match_key] in existing:
                            existing[item[match_key]].update(item)
                        else:
                            result[key].append(item)
                else:
                    result[key] = value
    return result


def get_ip_address():
    """
    获取IP地址
    """
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except OSError:
        return "未知"


def get_epg_url():
    """
    获取EPG结果URL
    """
    return config.epg_url


def convert_to_m3u(path=None, first_channel_name=None, data=None):
    """
    将结果TXT文件转换为M3U格式
    """
    if path and data:
        with open(path, 'w', encoding='utf-8') as file:
            file.write("#EXTM3U\n")
            for category, channels in data.items():
                for name, infos in channels.items():
                    for info in infos:
                        file.write(f"#EXTINF:-1 tvg-id=\"{name}\" tvg-name=\"{name}\" tvg-logo=\"{info.get('logo', '')}\" group-title=\"{category}\",{name}\n")
                        file.write(f"{info['url']}\n")


def get_result_file_content(path=None, show_content=False, file_type=None):
    """
    获取结果文件的内容
    """
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
    """
    从数据列表中移除重复项
    """
    unique_list = []
    for item in data_list:
        url = item['url']
        if filter_host:
            host = get_url_host(url)
            if host in seen:
                continue
            seen.add(host)
        elif url in seen:
            continue
        seen.add(url)
        unique_list.append(item)
    return unique_list


def process_nested_dict(data, seen, filter_host=False, ipv6_support=True):
    """
    处理嵌套字典
    """
    for category, channels in data.items():
        for name, infos in channels.items():
            data[category][name] = remove_duplicates_from_list(infos, seen, filter_host, ipv6_support)
    return data


def get_url_host(url):
    """
    获取URL的主机名
    """
    from urllib.parse import urlparse
    parsed = urlparse(url)
    return parsed.hostname


def add_url_info(url, info):
    """
    向URL添加信息
    """
    return f"{url}?{info}"


def format_url_with_cache(url, cache=None):
    """
    用缓存格式化URL
    """
    if cache and url in cache:
        return add_url_info(url, cache[url])
    return url


def remove_cache_info(string):
    """
    从字符串中移除缓存信息
    """
    return string.split('?')[0]


def resource_path(relative_path, persistent=False):
    """
    获取资源路径
    """
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
    """
    将内容写入TXT文件
    """
    if path:
        if position:
            with open(path, 'r+', encoding='utf-8') as file:
                lines = file.readlines()
                lines.insert(position, content)
                file.seek(0)
                file.writelines(lines)
        else:
            with open(path, 'a', encoding='utf-8') as file:
                file.write(content)
        if callback:
            callback()


def format_name(name: str) -> str:
    """
    格式化名称，进行替换和小写处理
    """
    return re.sub(r'[^\w\s]', '', name).strip().lower()


def get_headers_key_value(content: str) -> dict:
    """
    从内容中获取头信息的键值对
    """
    headers = {}
    for line in content.splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            headers[key.strip()] = value.strip()
    return headers


def get_name_url(content, pattern, open_headers=False, check_url=True):
    """
    使用正则表达式从内容中提取名称和URL
    """
    matches = pattern.findall(content)
    results = []
    for match in matches:
        name, url = match
        if check_url and not url.startswith(('http', 'rtmp')):
            continue
        if open_headers:
            headers = get_headers_key_value(name)
            name = headers.pop('name', name)
            result = {'name': name, 'url': url, 'headers': headers}
        else:
            result = {'name': name, 'url': url}
        results.append(result)
    return results


def get_real_path(path) -> str:
    """
    获取真实路径
    """
    return os.path.realpath(path)


def get_urls_from_file(path: str, pattern_search: bool = True) -> list:
    """
    从文件中获取URL列表
    """
    urls = []
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    if pattern_search:
                        # 可以添加正则匹配逻辑
                        urls.append(line)
                    else:
                        urls.append(line)
    return urls


def get_name_urls_from_file(path: str, format_name_flag: bool = False) -> dict[str, list]:
    """
    从文件中获取名称和URL列表
    """
    name_urls = defaultdict(list)
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as file:
            content = file.read()
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
    """
    从目录中获取名称和URI，仅从文件名获取
    """
    name_uri = {}
    if os.path.exists(path):
        for root, dirs, files in os.walk(path):
            for file in files:
                name = os.path.splitext(file)[0]
                uri = os.path.join(root, file)
                name_uri[name] = uri
    return name_uri


def get_datetime_now():
    """
    获取当前日期和时间
    """
    return datetime.datetime.now(pytz.timezone('Asia/Shanghai'))


def get_version_info():
    """
    获取版本信息
    """
    return {
        'name': 'IPTV-API',
        'version': '1.0.0'
    }


def join_url(url1: str, url2: str) -> str:
    """
    拼接URL
    """
    from urllib.parse import urljoin
    return urljoin(url1, url2)


def find_by_id(data: dict, id: int) -> dict:
    """
    通过ID查找嵌套字典
    """
    def _find(data):
        if isinstance(data, dict):
            if 'id' in data and data['id'] == id:
                return data
            for value in data.values():
                result = _find(value)
                if result:
                    return result
        elif isinstance(data, list):
            for item in data:
                result = _find(item)
                if result:
                    return result
        return None

    return _find(data)


def custom_print(*args, **kwargs):
    """
    自定义打印函数
    """
    print(*args, **kwargs)


def get_urls_len(data) -> int:
    """
    获取字典中URL的数量
    """
    count = 0
    for category in data.values():
        for channel in category.values():
            count += len(channel)
    return count
