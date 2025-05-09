import asyncio
import base64
import gzip
import json
import os
import pickle
import re
from collections import defaultdict
from logging import INFO

from bs4 import NavigableString

import utils.constants as constants
from updates.epg.tools import write_to_xml, compress_to_gz
from utils.alias import Alias
from utils.config import config
from utils.db import get_db_connection, return_db_connection
from utils.ip_checker import IPChecker
from utils.speed import (
    get_speed,
    get_speed_result,
    get_sort_result,
    check_ffmpeg_installed_status
)
from utils.tools import (
    format_name,
    get_name_url,
    check_url_by_keywords,
    get_total_urls,
    add_url_info,
    resource_path,
    get_urls_from_file,
    get_name_urls_from_file,
    get_logger,
    get_datetime_now,
    get_url_host,
    check_ipv_type_match,
    get_ip_address,
    convert_to_m3u,
    custom_print,
    get_name_uri_from_dir,
    get_resolution_value
)
from utils.types import ChannelData, OriginType, CategoryChannelData

channel_alias = Alias()
ip_checker = IPChecker()
frozen_channels = set()
location_list = config.location
isp_list = config.isp


def format_channel_data(url: str, origin: OriginType) -> ChannelData:
    """
    格式化频道数据，返回标准化的频道数据结构
    """
    # 初始化频道数据
    channel_data: ChannelData = {
        'url': url,
        'origin': origin,
        'create_time': get_datetime_now(),
        'status': 'unknown',
        'speed': -1,
        'delay': -1,
        'ipv_type': 'unknown',
        'resolution': 'unknown',
        'format': 'unknown',
        'headers': {},
        'extra_info': {}
    }
    
    # 检查URL类型
    if url.startswith('http'):
        if url.endswith('.m3u8'):
            channel_data['format'] = 'hls'
        elif url.endswith(('.mp4', '.flv', '.avi')):
            channel_data['format'] = url.split('.')[-1]
        else:
            channel_data['format'] = 'http'
    elif url.startswith('rtmp'):
        channel_data['format'] = 'rtmp'
    elif url.startswith('rtsp'):
        channel_data['format'] = 'rtsp'
    
    # 检查IP类型
    host = get_url_host(url)
    if host:
        if ':' in host:  # 简单判断IPv6
            channel_data['ipv_type'] = 'ipv6'
        else:
            channel_data['ipv_type'] = 'ipv4'
    
    return channel_data


def get_channel_data_from_file(channels, file, whitelist, open_local=config.open_local,
                               local_data=None, live_data=None, hls_data=None) -> CategoryChannelData:
    """
    从文件中获取频道数据，支持本地源文件和各种格式
    """
    result: CategoryChannelData = defaultdict(lambda: defaultdict(list))
    
    # 如果不启用本地源，直接返回空结果
    if not open_local:
        return result
    
    # 如果提供了文件路径，读取文件内容
    if file and os.path.exists(file):
        # 获取名称和URL列表
        name_urls = get_name_urls_from_file(file, format_name_flag=True)
        
        for name, urls in name_urls.items():
            # 检查是否在白名单中
            is_whitelisted = name in whitelist
            
            for url in urls:
                # 检查是否在黑名单中
                if not check_url_by_keywords(url, get_urls_from_file(constants.blacklist_path)):
                    continue
                
                # 格式化频道数据
                channel_data = format_channel_data(url, OriginType.LOCAL)
                
                # 添加到结果中
                if name in channels:
                    # 如果名称在预定义频道列表中，使用对应的分类
                    category = channels[name]['category']
                    result[category][name].append(channel_data)
                else:
                    # 否则使用默认分类
                    result["其他"][name].append(channel_data)
    
    # 处理本地数据、直播数据和HLS数据
    if local_data:
        # 处理本地数据逻辑
        pass
    
    if live_data:
        # 处理直播数据逻辑
        pass
    
    if hls_data:
        # 处理HLS数据逻辑
        pass
    
    return result


def get_channel_items() -> CategoryChannelData:
    """
    从源文件中获取频道项，构建频道数据结构
    """
    result: CategoryChannelData = defaultdict(lambda: defaultdict(list))
    source_file = config.source_file
    
    if not os.path.exists(source_file):
        print(f"源文件不存在: {source_file}")
        return result
    
    # 获取名称和URL列表
    name_urls = get_name_urls_from_file(source_file, format_name_flag=True)
    
    # 假设源文件中的频道已经分类，格式为 "分类/频道名"
    for full_name, urls in name_urls.items():
        # 分割分类和频道名
        parts = full_name.split('/', 1)
        if len(parts) == 2:
            category, name = parts
        else:
            category = "其他"
            name = parts[0]
        
        # 为每个URL创建频道数据
        for url in urls:
            # 格式化频道数据
            channel_data = format_channel_data(url, OriginType.SOURCE)
            
            # 添加到结果中
            result[category][name].append(channel_data)
    
    return result


def format_channel_name(name):
    """
    格式化频道名称，进行替换和小写处理
    """
    return format_name(name)


def channel_name_is_equal(name1, name2):
    """
    检查频道名称是否相等，使用格式化后的名称进行比较
    """
    return format_channel_name(name1) == format_channel_name(name2)


def get_channel_results_by_name(name, data):
    """
    从数据中按名称获取频道结果，支持别名匹配
    """
    formatted_name = format_channel_name(name)
    results = []
    
    # 先尝试直接匹配
    for category, channels in data.items():
        for channel_name, channel_list in channels.items():
            if format_channel_name(channel_name) == formatted_name:
                results.extend(channel_list)
                return results  # 找到后直接返回
    
    # 尝试使用别名匹配
    aliases = channel_alias.get_aliases(name)
    for alias in aliases:
        for category, channels in data.items():
            for channel_name, channel_list in channels.items():
                if format_channel_name(channel_name) == format_channel_name(alias):
                    results.extend(channel_list)
                    return results  # 找到后直接返回
    
    return results


def get_element_child_text_list(element, child_name):
    """
    获取元素的子元素文本列表
    """
    text_list = []
    if not element:
        return text_list
    
    # 查找所有指定名称的子元素
    for child in element.find_all(child_name):
        text = child.get_text(strip=True)
        if text:
            text_list.append(text)
    
    return text_list


def get_multicast_ip_list(urls):
    """
    从URL列表中获取组播IP列表
    """
    multicast_ips = []
    if not urls:
        return multicast_ips
    
    # 组播IP地址范围 (224.0.0.0 - 239.255.255.255)
    multicast_pattern = re.compile(r'(22[4-9]|23[0-9])\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)')
    
    for url in urls:
        # 从URL中提取IP地址
        match = multicast_pattern.search(url)
        if match:
            multicast_ips.append(match.group(0))
    
    return multicast_ips


def get_channel_multicast_region_ip_list(result, channel_region, channel_type):
    """
    从结果中按地区和类型获取频道组播IP列表
    """
    ip_list = []
    
    for category, channels in result.items():
        for name, channel_list in channels.items():
            # 检查频道地区和类型
            if channel_region and channel_region not in name:
                continue
            
            if channel_type and channel_type not in name:
                continue
            
            # 获取组播IP
            for channel in channel_list:
                if channel.get('ipv_type') == 'ipv4':  # 组播通常是IPv4
                    urls = [channel.get('url')]
                    ips = get_multicast_ip_list(urls)
                    ip_list.extend(ips)
    
    return ip_list


def get_channel_multicast_name_region_type_result(result, names):
    """
    从结果中按名称、地区和类型获取组播结果
    """
    filtered_result: CategoryChannelData = defaultdict(lambda: defaultdict(list))
    
    for category, channels in result.items():
        for name, channel_list in channels.items():
            # 检查名称是否在列表中
            if names and format_channel_name(name) not in [format_channel_name(n) for n in names]:
                continue
            
            # 检查是否有组播IP
            has_multicast = False
            for channel in channel_list:
                if channel.get('ipv_type') == 'ipv4':
                    urls = [channel.get('url')]
                    ips = get_multicast_ip_list(urls)
                    if ips:
                        has_multicast = True
                        break
            
            # 如果有组播IP，添加到结果中
            if has_multicast:
                filtered_result[category][name] = channel_list
    
    return filtered_result


def get_channel_multicast_region_type_list(result):
    """
    从结果中获取频道组播地区和类型列表
    """
    regions = set()
    types = set()
    
    for category, channels in result.items():
        for name, channel_list in channels.items():
            # 检查是否有组播IP
            has_multicast = False
            for channel in channel_list:
                if channel.get('ipv_type') == 'ipv4':
                    urls = [channel.get('url')]
                    ips = get_multicast_ip_list(urls)
                    if ips:
                        has_multicast = True
                        break
            
            # 如果有组播IP，分析地区和类型
            if has_multicast:
                # 简单分析，假设名称格式为 "地区-类型-频道名"
                parts = name.split('-')
                if len(parts) >= 2:
                    regions.add(parts[0])
                    types.add(parts[1])
    
    return list(regions), list(types)


def get_channel_multicast_result(result, search_result):
    """
    从结果和搜索结果中获取频道组播信息结果
    """
    # 合并两个结果中的组播频道
    combined_result: CategoryChannelData = defaultdict(lambda: defaultdict(list))
    
    # 处理原始结果中的组播频道
    for category, channels in result.items():
        for name, channel_list in channels.items():
            # 检查是否有组播IP
            has_multicast = False
            multicast_channels = []
            for channel in channel_list:
                if channel.get('ipv_type') == 'ipv4':
                    urls = [channel.get('url')]
                    ips = get_multicast_ip_list(urls)
                    if ips:
                        has_multicast = True
                        multicast_channels.append(channel)
            
            # 如果有组播IP，添加到结果中
            if has_multicast:
                combined_result[category][name] = multicast_channels
    
    # 处理搜索结果中的组播频道
    for category, channels in search_result.items():
        for name, channel_list in channels.items():
            # 检查是否有组播IP
            has_multicast = False
            multicast_channels = []
            for channel in channel_list:
                if channel.get('ipv_type') == 'ipv4':
                    urls = [channel.get('url')]
                    ips = get_multicast_ip_list(urls)
                    if ips:
                        has_multicast = True
                        multicast_channels.append(channel)
            
            # 如果有组播IP且不在原始结果中，添加到结果中
            if has_multicast and name not in combined_result.get(category, {}):
                combined_result[category][name] = multicast_channels
    
    return combined_result


def get_results_from_soup(soup, name):
    """
    从BeautifulSoup对象中获取结果，解析HTML内容
    """
    results = []
    if not soup:
        return results
    
    # 根据名称查找相关元素
    # 这里的实现取决于具体的HTML结构
    # 以下是一个示例实现
    elements = soup.find_all(string=re.compile(name, re.IGNORECASE))
    
    for element in elements:
        # 获取父元素或相关元素
        parent = element.parent
        if parent:
            # 查找包含URL的元素
            url_element = parent.find('a')
            if url_element and url_element.get('href'):
                url = url_element.get('href')
                results.append({
                    'name': element.strip(),
                    'url': url,
                    'source': 'web'
                })
    
    return results


def get_results_from_multicast_soup(soup, hotel=False):
    """
    从组播的BeautifulSoup对象中获取结果
    """
    results = []
    if not soup:
        return results
    
    # 组播源通常有特定的格式
    # 以下是一个示例实现，根据实际情况调整
    if hotel:
        # 酒店组播源的解析逻辑
        elements = soup.find_all('tr')
        for element in elements:
            # 查找包含频道名和组播地址的单元格
            tds = element.find_all('td')
            if len(tds) >= 2:
                name = tds[0].get_text(strip=True)
                url = tds[1].get_text(strip=True)
                
                # 检查是否是有效的组播地址
                if url.startswith(('rtp://', 'udp://')) or get_multicast_ip_list([url]):
                    results.append({
                        'name': name,
                        'url': url,
                        'source': 'hotel_multicast'
                    })
    else:
        # 普通组播源的解析逻辑
        elements = soup.find_all('li')
        for element in elements:
            # 查找包含频道名和组播地址的链接
            a = element.find('a')
            if a and a.get('href'):
                name = a.get_text(strip=True)
                url = a.get('href')
                
                # 检查是否是有效的组播地址
                if url.startswith(('rtp://', 'udp://')) or get_multicast_ip_list([url]):
                    results.append({
                        'name': name,
                        'url': url,
                        'source': 'multicast'
                    })
    
    return results


def get_results_from_soup_requests(soup, name):
    """
    通过请求从BeautifulSoup对象中获取结果
    """
    results = []
    if not soup:
        return results
    
    # 查找包含名称的元素，并获取相关链接
    elements = soup.find_all(string=re.compile(name, re.IGNORECASE))
    
    for element in elements:
        # 获取父元素
        parent = element.parent
        if parent:
            # 查找链接元素
            link = parent.find('a')
            if link and link.get('href'):
                url = link.get('href')
                
                # 如果是相对URL，构建完整URL
                if not url.startswith(('http', 'https')):
                    base_url = soup.base.get('href') if soup.base else ''
                    if base_url:
                        url = join_url(base_url, url)
                
                # 发送请求获取详细信息
                try:
                    response = requests.get(url)
                    if response.status_code == 200:
                        # 解析响应内容
                        detail_soup = BeautifulSoup(response.text, 'html.parser')
                        # 提取详细信息
                        # 这里的实现取决于具体的页面结构
                        detail_info = {
                            'name': name,
                            'url': url,
                            'source': 'web_request'
                        }
                        results.append(detail_info)
                except Exception as e:
                    print(f"Error fetching {url}: {e}")
    
    return results


def get_results_from_multicast_soup_requests(soup, hotel=False):
    """
    通过请求从组播的BeautifulSoup对象中获取结果
    """
    results = []
    if not soup:
        return results
    
    # 获取组播链接列表
    links = []
    if hotel:
        # 酒店组播源的链接提取逻辑
        elements = soup.find_all('a', href=re.compile(r'(rtp|udp)://'))
        for element in elements:
            links.append({
                'name': element.get_text(strip=True),
                'url': element.get('href')
            })
    else:
        # 普通组播源的链接提取逻辑
        elements = soup.find_all('a')
        for element in elements:
            url = element.get('href')
            if url and (url.startswith(('rtp://', 'udp://')) or get_multicast_ip_list([url])):
                links.append({
                    'name': element.get_text(strip=True),
                    'url': url
                })
    
    # 对每个链接发送请求获取详细信息
    for link in links:
        try:
            response = requests.get(link['url'])  # 注意：某些组播URL可能无法直接请求
            if response.status_code == 200:
                # 解析响应内容
                detail_soup = BeautifulSoup(response.text, 'html.parser')
                # 提取详细信息
                # 这里的实现取决于具体的页面结构
                detail_info = {
                    'name': link['name'],
                    'url': link['url'],
                    'source': 'multicast_request'
                }
                results.append(detail_info)
        except Exception as e:
            print(f"Error fetching {link['url']}: {e}")
    
    return results


def get_channel_url(text):
    """
    从文本中获取URL
    """
    if not text:
        return None
    
    # 使用正则表达式匹配URL
    url_pattern = re.compile(r'(https?|rtmp|rtsp|mms|rtp|udp)://\S+')
    match = url_pattern.search(text)
    
    if match:
        return match.group(0)
    
    return None


def get_channel_info(text):
    """
    从文本中获取频道信息
    """
    if not text:
        return {}
    
    # 假设文本格式为 "频道名,URL" 或 "频道名|URL" 等
    separators = [',', '|', ' ', '\t']
    
    for separator in separators:
        if separator in text:
            parts = text.split(separator, 1)
            if len(parts) == 2:
                name = parts[0].strip()
                url = get_channel_url(parts[1])
                if url:
                    return {
                        'name': name,
                        'url': url
                    }
    
    # 如果没有找到分隔符，尝试直接提取URL
    url = get_channel_url(text)
    if url:
        return {
            'name': '未知频道',
            'url': url
        }
    
    return {}


def get_multicast_channel_info(text):
    """
    从文本中获取组播频道信息
    """
    if not text:
        return {}
    
    # 组播频道通常有特定的格式
    # 例如: "CCTV-1,rtp://239.1.1.1:1234"
    # 或: "北京卫视|udp://239.2.2.2:5678"
    
    # 先尝试使用通用的频道信息提取函数
    info = get_channel_info(text)
    
    # 检查是否是组播URL
    if info.get('url') and (info['url'].startswith(('rtp://', 'udp://')) or get_multicast_ip_list([info['url']])):
        return info
    
    # 如果不是，尝试其他格式
    # 例如: "239.1.1.1:1234,CCTV-1"
    url_pattern = re.compile(r'((rtp|udp)://)?(22[4-9]|23[0-9])\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.(25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?):(\d+)')
    match = url_pattern.search(text)
    
    if match:
        url = match.group(0)
        if not url.startswith(('rtp://', 'udp://')):
            url = 'rtp://' + url
        
        # 提取频道名
        name = text.replace(match.group(0), '').strip()
        if name.startswith((':', ',', '|', ' ')):
            name = name[1:].strip()
        
        if not name:
            name = "未知组播频道"
        
        return {
            'name': name,
            'url': url,
            'ipv_type': 'ipv4',
            'format': 'multicast'
        }
    
    return {}


def init_info_data(data: dict, category: str, name: str) -> None:
    """
    初始化频道信息数据结构
    """
    if category not in data:
        data[category] = {}
    
    if name not in data[category]:
        data[category][name] = []


def append_data_to_info_data(
        info_data: dict,
        category: str,
        name: str,
        data: list,
        origin: str = None,
        check: bool = True,
        whitelist: list = None,
        blacklist: list = None,
        ipv_type_data: dict = None
) -> None:
    """
    将频道数据添加到总信息数据中，并进行去重和验证
    """
    if not data or not name:
        return
    
    # 初始化数据结构
    init_info_data(info_data, category, name)
    
    # 获取已存在的数据
    existing_data = info_data[category][name]
    
    # 处理白名单
    if whitelist and name in whitelist:
        # 白名单中的频道优先处理
        for item in data:
            if isinstance(item, dict) and 'url' in item:
                url = item['url']
                
                # 检查黑名单
                if blacklist and not check_url_by_keywords(url, blacklist):
                    continue
                
                # 检查IP类型
                if ipv_type_data and not check_ipv_type_match(item.get('ipv_type', 'unknown'), ipv_type_data):
                    continue
                
                # 添加到现有数据
                existing_data.append(item)
    
    # 处理普通数据
    for item in data:
        if isinstance(item, dict) and 'url' in item:
            url = item['url']
            
            # 检查黑名单
            if blacklist and not check_url_by_keywords(url, blacklist):
                continue
            
            # 检查IP类型
            if ipv_type_data and not check_ipv_type_match(item.get('ipv_type', 'unknown'), ipv_type_data):
                continue
            
            # 检查重复
            if check and any(d.get('url') == url for d in existing_data):
                continue
            
            # 添加来源信息
            if origin:
                item['origin'] = origin
            
            # 添加到现有数据
            existing_data.append(item)


def get_origin_method_name(method):
    """
    获取来源方法名称
    """
    origin_methods = {
        "hotel_fofa": "酒店FOFA",
        "multicast": "组播",
        "hotel_foodie": "酒店美食",
        "subscribe": "订阅源",
        "online_search": "在线搜索",
        "local": "本地源",
        "source": "源文件"
    }
    
    return origin_methods.get(method, method)


def append_old_data_to_info_data(info_data, cate, name, data, whitelist=None, blacklist=None, ipv_type_data=None):
    """
    将历史和本地频道数据添加到总信息数据中
    """
    if not data or not name:
        return
    
    # 初始化数据结构
    init_info_data(info_data, cate, name)
    
    # 获取已存在的数据
    existing_data = info_data[cate][name]
    
    # 处理历史和本地数据
    for item in data:
        if isinstance(item, dict) and 'url' in item:
            url = item['url']
            
            # 检查黑名单
            if blacklist and not check_url_by_keywords(url, blacklist):
                continue
            
            # 检查IP类型
            if ipv_type_data and not check_ipv_type_match(item.get('ipv_type', 'unknown'), ipv_type_data):
                continue
            
            # 检查重复
            if any(d.get('url') == url for d in existing_data):
                continue
            
            # 添加到现有数据
            existing_data.append(item)


def print_channel_number(data: CategoryChannelData, cate: str, name: str):
    """
    打印频道数量
    """
    if cate in data and name in data[cate]:
        count = len(data[cate][name])
        print(f"频道: {name} ({cate}), 来源数量: {count}")
    else:
        print(f"未找到频道: {name} ({cate})")


def append_total_data(
        items,
        data,
        hotel_fofa_result=None,
        multicast_result=None,
        hotel_foodie_result=None,
        subscribe_result=None,
        online_search_result=None,
):
    """
    将所有方法的数据添加到总信息数据中
    """
    # 获取黑名单和白名单
    blacklist = get_urls_from_file(constants.blacklist_path)
    whitelist = get_urls_from_file(constants.whitelist_path)
    
    # 获取IP类型偏好
    ipv6_support = config.ipv6_support
    ipv_type_prefer = ['ipv4', 'ipv6'] if ipv6_support else ['ipv4']
    
    # 处理源文件数据
    for (category, name), channel_list in items:
        # 确保数据结构存在
        if category not in data:
            data[category] = {}
        if name not in data[category]:
            data[category][name] = []
        
        # 添加源文件数据
        for channel in channel_list:
            data[category][name].append(channel)
    
    # 处理其他来源的数据
    origin_methods = [
        ("hotel_fofa", hotel_fofa_result, "酒店FOFA"),
        ("multicast", multicast_result, "组播"),
        ("hotel_foodie", hotel_foodie_result, "酒店美食"),
        ("subscribe", subscribe_result, "订阅源"),
        ("online_search", online_search_result, "在线搜索"),
    ]
    
    for method, result, origin_name in origin_methods:
        if not result:
            continue
        
        for category, channels in result.items():
            for name, channel_list in channels.items():
                # 添加到总数据中
                append_data_to_info_data(
                    data,
                    category,
                    name,
                    channel_list,
                    origin=origin_name,
                    check=True,
                    whitelist=whitelist,
                    blacklist=blacklist,
                    ipv_type_data=ipv_type_prefer
                )


async def test_speed(data, ipv6=False, callback=None):
    """
    测试频道数据的速度
    """
    test_results = {}
    if not data:
        return test_results
    
    # 获取所有需要测试的URL
    all_urls = []
    for category, channels in data.items():
        for name, channel_list in channels.items():
            for channel in channel_list:
                url = channel.get('url')
                if url:
                    all_urls.append({
                        'category': category,
                        'name': name,
                        'url': url,
                        'origin': channel.get('origin'),
                        'ipv_type': channel.get('ipv_type', 'unknown')
                    })
    
    # 过滤掉不支持的IP类型
    if not ipv6:
        all_urls = [u for u in all_urls if u.get('ipv_type') != 'ipv6']
    
    # 异步测试所有URL的速度
    async def test_single_url(url_info):
        url = url_info['url']
        result = await get_speed(url)
        
        # 调用回调函数更新进度
        if callback:
            callback()
        
        return {
            'category': url_info['category'],
            'name': url_info['name'],
            'url': url,
            'speed': result.get('speed', -1),
            'delay': result.get('delay', -1),
            'status': result.get('status', 'unknown'),
            'test_time': get_datetime_now()
        }
    
    # 创建异步任务列表
    tasks = [test_single_url(url_info) for url_info in all_urls]
    
    # 执行所有任务
    results = await asyncio.gather(*tasks)
    
    # 整理结果
    for result in results:
        category = result['category']
        name = result['name']
        url = result['url']
        
        if category not in test_results:
            test_results[category] = {}
        
        if name not in test_results[category]:
            test_results[category][name] = []
        
        test_results[category][name].append(result)
    
    return test_results


def sort_channel_result(channel_data, result=None, filter_host=False, ipv6_support=True):
    """
    对频道结果进行排序，根据测速结果和其他因素
    """
    sorted_data = defaultdict(lambda: defaultdict(list))
    
    # 获取IP类型偏好
    ipv_type_prefer = ['ipv4', 'ipv6'] if ipv6_support else ['ipv4']
    
    # 遍历所有频道
    for category, channels in channel_data.items():
        for name, channel_list in channels.items():
            # 获取该频道的测速结果
            test_info = []
            if result and category in result and name in result[category]:
                test_info = result[category][name]
            
            # 为每个频道URL添加测速结果
            for channel in channel_list:
                url = channel.get('url')
                channel_test_info = next((t for t in test_info if t.get('url') == url), None)
                
                if channel_test_info:
                    # 添加测速结果到频道信息
                    channel['speed'] = channel_test_info.get('speed', -1)
                    channel['delay'] = channel_test_info.get('delay', -1)
                    channel['status'] = channel_test_info.get('status', 'unknown')
                    channel['test_time'] = channel_test_info.get('test_time')
            
            # 过滤不支持的IP类型
            filtered_channels = [
                channel for channel in channel_list
                if check_ipv_type_match(channel.get('ipv_type', 'unknown'), ipv_type_prefer)
            ]
            
            # 排序
            sorted_channels = sorted(
                filtered_channels,
                key=lambda x: (
                    # 优先排序状态良好的
                    0 if x.get('status') == 'good' else 1 if x.get('status') == 'ok' else 2,
                    # 其次排序速度快的
                    -x.get('speed', -1),
                    # 再其次排序延迟低的
                    x.get('delay', float('inf')),
                    # 最后排序创建时间新的
                    -x.get('create_time', 0) if isinstance(x.get('create_time'), int) else 0
                )
            )
            
            # 添加到排序结果
            sorted_data[category][name] = sorted_channels
    
    return sorted_data


def process_write_content(
        path: str,
        data: CategoryChannelData,
        live: bool = False,
        hls: bool = False,
        live_url: str = None,
        hls_url: str = None,
        open_empty_category: bool = False,
        ipv_type_prefer: list[str] = None,
        origin_type_prefer: list[str] = None,
        first_channel_name: str = None,
        enable_print: bool = False
):
    """
    获取频道写入内容，生成M3U或其他格式的内容
    """
    content = "#EXTM3U\n"
    
    # 用于记录已添加的频道
    added_channels = set()
    
    # 处理每个分类
    for category, channels in data.items():
        # 如果该分类为空且不显示空分类，跳过
        if not channels and not open_empty_category:
            continue
        
        # 添加分类标题
        content += f"#EXTGRP:{category}\n"
        
        # 处理该分类下的每个频道
        for name, channel_list in channels.items():
            # 检查是否已添加该频道
            if name in added_channels:
                continue
            
            # 过滤IP类型和来源类型
            filtered_channels = []
            for channel in channel_list:
                # 检查IP类型
                if ipv_type_prefer and not check_ipv_type_match(channel.get('ipv_type', 'unknown'), ipv_type_prefer):
                    continue
                
                # 检查来源类型
                if origin_type_prefer and channel.get('origin') not in origin_type_prefer:
                    continue
                
                # 检查是否符合直播或HLS要求
                if live and channel.get('format') != 'live':
                    continue
                
                if hls and channel.get('format') != 'hls':
                    continue
                
                filtered_channels.append(channel)
            
            # 如果没有符合条件的频道，跳过
            if not filtered_channels:
                continue
            
            # 获取最佳频道（已排序）
            best_channel = filtered_channels[0]
            url = best_channel.get('url')
            if not url:
                continue
            
            # 添加频道信息
            extinf = f"#EXTINF:-1"
            
            # 添加标签信息
            tags = []
            if best_channel.get('status') == 'good':
                tags.append('稳定')
            elif best_channel.get('status') == 'ok':
                tags.append('一般')
            else:
                tags.append('未知')
            
            if best_channel.get('speed') > 0:
                tags.append(f"{best_channel['speed']:.2f}Mbps")
            
            if best_channel.get('delay') > 0:
                tags.append(f"{best_channel['delay']}ms")
            
            if tags:
                extinf += f" tag=\"{','.join(tags)}\""
            
            # 添加来源信息
            origin = best_channel.get('origin')
            if origin:
                extinf += f" group-title=\"{origin}\""
            
            # 添加分辨率信息
            resolution = best_channel.get('resolution')
            if resolution and resolution != 'unknown':
                extinf += f" tvg-resolution=\"{resolution}\""
            
            # 添加频道名称
            extinf += f",{name}\n"
            
            # 添加到内容中
            content += extinf
            
            # 如果是直播或HLS，添加相关URL信息
            if live and live_url:
                content += f"{live_url}/{name}\n"
            elif hls and hls_url:
                content += f"{hls_url}/{name}.m3u8\n"
            else:
                content += f"{url}\n"
            
            # 标记为已添加
            added_channels.add(name)
            
            # 如果是第一个频道，记录位置
            if first_channel_name and name == first_channel_name:
                first_channel_position = len(content)
    
    return content


def write_channel_to_file(data, epg=None, ipv6=False, first_channel_name=None):
    """
    将频道数据写入文件，生成M3U和EPG文件
    """
    # 获取配置
    final_file = config.final_file
    output_dir = os.path.dirname(final_file)
    
    # 确保输出目录存在
    if not os.path.exists(output_dir):
        os.makedirs(output_dir)
    
    # 获取IP类型偏好
    ipv_type_prefer = ['ipv4', 'ipv6'] if ipv6 else ['ipv4']
    
    # 生成M3U文件内容
    m3u_content = process_write_content(
        final_file,
        data,
        live=False,
        hls=False,
        open_empty_category=False,
        ipv_type_prefer=ipv_type_prefer,
        first_channel_name=first_channel_name,
        enable_print=True
    )
    
    # 写入M3U文件
    with open(final_file, 'w', encoding='utf-8') as f:
        f.write(m3u_content)
    
    print(f"✅ M3U文件已生成: {final_file}")
    
    # 生成EPG文件
    if epg and config.open_method['epg']:
        epg_path = os.path.join(output_dir, "epg.xml")
        
        # 写入EPG文件
        write_to_xml(epg, epg_path)
        print(f"✅ EPG文件已生成: {epg_path}")
        
        # 压缩EPG文件为GZ格式
        epg_gz_path = os.path.join(output_dir, "epg.xml.gz")
        compress_to_gz(epg_path, epg_gz_path)
        print(f"✅ EPG GZ文件已生成: {epg_gz_path}")


def get_multicast_fofa_search_org(region, org_type):
    """
    获取组播FOFA搜索组织
    """
    # 根据地区和组织类型生成FOFA搜索条件
    # 这里只是示例，实际实现需要根据FOFA语法和数据源调整
    search_orgs = {
        "北京": {
            "教育": "institution=\"北京教育网络和信息中心\"",
            "政府": "institution=\"北京市政府\"",
            "企业": "institution=\"北京联通\""
        },
        "上海": {
            "教育": "institution=\"上海教育网络和信息中心\"",
            "政府": "institution=\"上海市政府\"",
            "企业": "institution=\"上海电信\""
        }
        # 其他地区和类型...
    }
    
    return search_orgs.get(region, {}).get(org_type, "")


def get_multicast_fofa_search_urls():
    """
    获取组播FOFA搜索URL列表
    """
    # 生成FOFA搜索URL列表
    # 这里只是示例，实际实现需要根据FOFA API和数据源调整
    search_urls = []
    
    # 获取配置的地区和ISP
    regions = config.location
    isps = config.isp
    
    # 为每个地区和ISP组合生成搜索URL
    for region in regions:
        for isp in isps:
            # 获取搜索组织条件
            search_org = get_multicast_fofa_search_org(region, isp)
            
            # 构建FOFA搜索URL
            if search_org:
                search_query = f"rtp:// || udp:// && {search_org}"
                search_url = f"https://fofa.so/result?qbase64={base64.b64encode(search_query.encode()).decode()}"
                search_urls.append(search_url)
    
    return search_urls


def get_channel_data_cache_with_compare(data, new_data):
    """
    获取频道数据，并与新数据进行比较
    """
    # 合并新旧数据，保留最新的信息
    merged_data = defaultdict(lambda: defaultdict(list))
    
    # 先处理新数据
    for category, channels in new_data.items():
        for name, channel_list in channels.items():
            merged_data[category][name] = channel_list
    
    # 再处理旧数据，只添加新数据中没有的频道
    for category, channels in data.items():
        for name, channel_list in channels.items():
            if name not in merged_data.get(category, {}):
                merged_data[category][name] = channel_list
            else:
                # 对于已存在的频道，只添加新数据中没有的URL
                existing_urls = {channel.get('url') for channel in merged_data[category][name]}
                for channel in channel_list:
                    if channel.get('url') not in existing_urls:
                        merged_data[category][name].append(channel)
    
    return merged_data
