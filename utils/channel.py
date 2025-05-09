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
    格式化频道数据
    """
    return {
        'url': url,
        'origin': origin,
        'speed': None,
        'resolution': None,
        'ipv_type': None
    }


def get_channel_data_from_file(channels, file, whitelist, open_local=config.open_local,
                               local_data=None, live_data=None, hls_data=None) -> CategoryChannelData:
    """
    从文件中获取频道数据
    """
    name_urls = get_name_urls_from_file(file)
    channel_data = defaultdict(lambda: defaultdict(list))
    for name, urls in name_urls.items():
        for url in urls:
            if check_url_by_keywords(url, whitelist):
                origin = 'local' if open_local else 'other'
                channel_data[channels.get(name, 'Unknown')][name].append(format_channel_data(url, origin))
    return channel_data


def get_channel_items() -> CategoryChannelData:
    """
    从源文件中获取频道项
    """
    source_file = config.source_file
    channels = {}
    if os.path.exists(source_file):
        with open(source_file, 'r', encoding='utf-8') as file:
            for line in file:
                line = line.strip()
                if line and not line.startswith('#'):
                    category, name = line.split(',', 1)
                    channels[name] = category
    return {category: {name: [] for name in names} for category, names in defaultdict(list, [(channels.get(name, 'Unknown'), [name]) for name in channels]).items()}


def format_channel_name(name):
    """
    格式化频道名称，进行替换和小写处理
    """
    return format_name(name)


def channel_name_is_equal(name1, name2):
    """
    检查频道名称是否相等
    """
    return format_channel_name(name1) == format_channel_name(name2)


def get_channel_results_by_name(name, data):
    """
    从数据中按名称获取频道结果
    """
    results = []
    for category, channels in data.items():
        for channel_name, infos in channels.items():
            if channel_name_is_equal(channel_name, name):
                results.extend(infos)
    return results


def get_element_child_text_list(element, child_name):
    """
    获取元素的子元素文本列表
    """
    return [child.text for child in element.find_all(child_name) if child.text]


def get_multicast_ip_list(urls):
    """
    从URL列表中获取组播IP列表
    """
    multicast_ips = []
    for url in urls:
        match = re.search(r'(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})', url)
        if match:
            ip = match.group(1)
            if ip.startswith(('224.', '225.', '226.', '227.', '228.', '229.', '230.', '231.', '232.', '233.', '234.', '235.', '236.', '237.', '238.', '239.')):
                multicast_ips.append(ip)
    return multicast_ips


def get_channel_multicast_region_ip_list(result, channel_region, channel_type):
    """
    从结果中按地区和类型获取频道组播IP列表
    """
    region_ip_list = []
    for item in result:
        if item.get('region') == channel_region and item.get('type') == channel_type:
            region_ip_list.extend(item.get('ips', []))
    return region_ip_list


def get_channel_multicast_name_region_type_result(result, names):
    """
    从结果中按名称、地区和类型获取组播结果
    """
    name_region_type_result = {}
    for item in result:
        name = item.get('name')
        if name in names:
            region = item.get('region')
            type_ = item.get('type')
            if (name, region, type_) not in name_region_type_result:
                name_region_type_result[(name, region, type_)] = []
            name_region_type_result[(name, region, type_)].extend(item.get('ips', []))
    return name_region_type_result


def get_channel_multicast_region_type_list(result):
    """
    从结果中获取频道组播地区和类型列表
    """
    region_type_list = []
    for item in result:
        region = item.get('region')
        type_ = item.get('type')
        if (region, type_) not in region_type_list:
            region_type_list.append((region, type_))
    return region_type_list


def get_channel_multicast_result(result, search_result):
    """
    从结果和搜索结果中获取频道组播信息结果
    """
    multicast_result = []
    for item in result:
        name = item.get('name')
        region = item.get('region')
        type_ = item.get('type')
        ips = item.get('ips', [])
        if (name, region, type_) in search_result:
            ips.extend(search_result[(name, region, type_)])
        multicast_result.append({
            'name': name,
            'region': region,
            'type': type_,
            'ips': ips
        })
    return multicast_result


def get_results_from_soup(soup, name):
    """
    从BeautifulSoup对象中获取结果
    """
    results = []
    # 实现解析逻辑
    return results


def get_results_from_multicast_soup(soup, hotel=False):
    """
    从组播的BeautifulSoup对象中获取结果
    """
    results = []
    # 实现解析逻辑
    return results


def get_results_from_soup_requests(soup, name):
    """
    通过请求从BeautifulSoup对象中获取结果
    """
    results = []
    # 实现解析逻辑
    return results


def get_results_from_multicast_soup_requests(soup, hotel=False):
    """
    通过请求从组播的BeautifulSoup对象中获取结果
    """
    results = []
    # 实现解析逻辑
    return results


def get_channel_url(text):
    """
    从文本中获取URL
    """
    match = re.search(r'(http[s]?://[^\s]+)', text)
    if match:
        return match.group(1)
    return None


def get_channel_info(text):
    """
    从文本中获取频道信息
    """
    info = {}
    # 实现解析逻辑
    return info


def get_multicast_channel_info(text):
    """
    从文本中获取组播频道信息
    """
    info = {}
    # 实现解析逻辑
    return info


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
    init_info_data(info_data, category, name)
    for item in data:
        url = item.get('url')
        if check:
            if whitelist and not check_url_by_keywords(url, whitelist):
                continue
            if blacklist and check_url_by_keywords(url, blacklist):
                continue
            if ipv_type_data:
                ipv_type = ip_checker.get_ipv_type(url)
                if not check_ipv_type_match(ipv_type, ipv_type_data.get('prefer_types', [])):
                    continue
                item['ipv_type'] = ipv_type
        if origin:
            item['origin'] = origin
        info_data[category][name].append(item)


def get_origin_method_name(method):
    """
    获取来源方法名称
    """
    return {
        'hotel_fofa': 'Hotel FOFA',
        'multicast': 'Multicast',
        'hotel_foodie': 'Hotel Foodie',
        'subscribe': 'Subscribe',
        'online_search': 'Online Search',
        'epg': 'EPG'
    }.get(method, method)


def append_old_data_to_info_data(info_data, cate, name, data, whitelist=None, blacklist=None, ipv_type_data=None):
    """
    将历史和本地频道数据添加到总信息数据中
    """
    append_data_to_info_data(info_data, cate, name, data, origin='old', check=True, whitelist=whitelist, blacklist=blacklist, ipv_type_data=ipv_type_data)


def print_channel_number(data: CategoryChannelData, cate: str, name: str):
    """
    打印频道数量
    """
    channels = data.get(cate, {}).get(name, [])
    print(f"{cate} - {name}: {len(channels)} channels")


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
    for category, channels in items:
        for name in channels:
            if hotel_fofa_result:
                append_data_to_info_data(data, category, name, hotel_fofa_result.get(name, []), origin='hotel_fofa')
            if multicast_result:
                append_data_to_info_data(data, category, name, multicast_result.get(name, []), origin='multicast')
            if hotel_foodie_result:
                append_data_to_info_data(data, category, name, hotel_foodie_result.get(name, []), origin='hotel_foodie')
            if subscribe_result:
                append_data_to_info_data(data, category, name, subscribe_result.get(name, []), origin='subscribe')
            if online_search_result:
                append_data_to_info_data(data, category, name, online_search_result.get(name, []), origin='online_search')


async def test_speed(data, ipv6=False, callback=None):
    """
    测试频道数据的速度
    """
    tasks = []
    for category, channels in data.items():
        for name, infos in channels.items():
            for info in infos:
                url = info['url']
                task = asyncio.create_task(get_speed(url, ipv6=ipv6, callback=callback))
                tasks.append(task)
    results = await asyncio.gather(*tasks)
    for category, channels in data.items():
        for name, infos in channels.items():
            for info in infos:
                url = info['url']
                for result in results:
                    if result['url'] == url:
                        info['speed'] = result['speed']
                        info['resolution'] = result['resolution']
                        break
    return data


def sort_channel_result(channel_data, result=None, filter_host=False, ipv6_support=True):
    """
    对频道结果进行排序
    """
    sorted_data = defaultdict(lambda: defaultdict(list))
    for category, channels in channel_data.items():
        for name, infos in channels.items():
            if result:
                info_results = get_channel_results_by_name(name, result)
                info_results.sort(key=lambda x: x.get('speed', float('inf')))
                for info in info_results:
                    url = info['url']
                    for original_info in infos:
                        if original_info['url'] == url:
                            sorted_data[category][name].append(original_info)
                            break
            else:
                sorted_data[category][name] = infos
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
    获取频道写入内容
    """
    content = ""
    for category, channels in data.items():
        if not channels and not open_empty_category:
            continue
        if enable_print:
            print(f"Category: {category}")
        for name, infos in channels.items():
            if enable_print:
                print(f"  Channel: {name}")
            urls = get_total_urls(infos, ipv_type_prefer, origin_type_prefer)
            for url in urls:
                if live:
                    url = add_url_info(url, f"live={live_url}")
                if hls:
                    url = add_url_info(url, f"hls={hls_url}")
                content += f"{category},{name},{url}\n"
    if path:
        with open(path, 'w', encoding='utf-8') as file:
            file.write(content)
    return content


def write_channel_to_file(data, epg=None, ipv6=False, first_channel_name=None):
    """
    将频道数据写入文件
    """
    final_file = config.final_file
    txt_file = os.path.splitext(final_file)[0] + ".txt"
    m3u_file = os.path.splitext(final_file)[0] + ".m3u"

    process_write_content(txt_file, data, enable_print=True)
    convert_to_m3u(m3u_file, first_channel_name, data)

    if epg:
        epg_path = os.path.join(os.path.dirname(final_file), "epg.xml")
        write_to_xml(epg, epg_path)
        epg_gz_path = os.path.join(os.path.dirname(final_file), "epg.gz")
        compress_to_gz(epg_path, epg_gz_path)


def get_multicast_fofa_search_org(region, org_type):
    """
    获取组播FOFA搜索组织
    """
    return f"{region} {org_type}"


def get_multicast_fofa_search_urls():
    """
    获取组播FOFA搜索URL列表
    """
    urls = []
    # 实现逻辑
    return urls


def get_channel_data_cache_with_compare(data, new_data):
    """
    获取频道数据，并与新数据进行比较
    """
    cache = {}
    if os.path.exists(constants.cache_path):
        with gzip.open(constants.cache_path, "rb") as file:
            try:
                cache = pickle.load(file)
            except EOFError:
                cache = {}
    merged_data = merge_objects(cache, new_data, match_key="url")
    return merged_data
