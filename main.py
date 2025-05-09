import asyncio
import copy
import gzip
import os
import pickle
from time import time

from tqdm import tqdm

import utils.constants as constants
from updates.epg import get_epg
from updates.fofa import get_channels_by_fofa
from updates.hotel import get_channels_by_hotel
from updates.multicast import get_channels_by_multicast
from updates.online_search import get_channels_by_online_search
from updates.subscribe import get_channels_by_subscribe_urls
from utils.channel import (
    get_channel_items,
    append_total_data,
    test_speed,
    write_channel_to_file,
    sort_channel_result,
)
from utils.config import config
from utils.tools import (
    get_pbar_remaining,
    get_ip_address,
    process_nested_dict,
    format_interval,
    check_ipv6_support,
    get_urls_from_file,
    get_version_info,
    join_url,
    get_urls_len,
    merge_objects
)
from utils.types import CategoryChannelData


class UpdateSource:
    """IPTV源更新管理器，负责协调各个数据源的更新和处理"""

    def __init__(self):
        """初始化更新源管理器"""
        self.update_progress = None  # 进度回调函数
        self.run_ui = False  # 是否运行在UI模式下
        self.tasks = []  # 异步任务列表
        self.channel_items: CategoryChannelData = {}  # 频道项目数据
        self.hotel_fofa_result = {}  # 酒店FOFA搜索结果
        self.hotel_foodie_result = {}  # 酒店美食频道结果
        self.multicast_result = {}  # 组播频道结果
        self.subscribe_result = {}  # 订阅源结果
        self.online_search_result = {}  # 在线搜索结果
        self.epg_result = {}  # EPG节目指南结果
        self.channel_data: CategoryChannelData = {}  # 最终频道数据
        self.pbar = None  # 进度条
        self.total = 0  # 总数
        self.start_time = None  # 开始时间

    async def visit_page(self, channel_names: list[str] = None):
        """访问并获取所有配置的频道源数据"""
        # 配置需要执行的任务
        tasks_config = [
            ("hotel_fofa", get_channels_by_fofa, "hotel_fofa_result"),
            ("multicast", get_channels_by_multicast, "multicast_result"),
            ("hotel_foodie", get_channels_by_hotel, "hotel_foodie_result"),
            ("subscribe", get_channels_by_subscribe_urls, "subscribe_result"),
            ("online_search", get_channels_by_online_search, "online_search_result"),
            ("epg", get_epg, "epg_result"),
        ]

        # 根据配置执行相应的数据源获取任务
        for setting, task_func, result_attr in tasks_config:
            # 跳过未启用的酒店相关任务
            if (setting == "hotel_foodie" or setting == "hotel_fofa") and config.open_hotel == False:
                continue
            # 执行启用的数据源任务
            if config.open_method[setting]:
                if setting == "subscribe":
                    # 获取订阅URL和白名单URL
                    subscribe_urls = get_urls_from_file(constants.subscribe_path)
                    whitelist_urls = get_urls_from_file(constants.whitelist_path)
                    # 如果配置了CDN，替换GitHub链接为CDN链接
                    if not os.getenv("GITHUB_ACTIONS") and config.cdn_url:
                        subscribe_urls = [join_url(config.cdn_url, url) if "raw.githubusercontent.com" in url else url
                                          for url in subscribe_urls]
                    # 创建异步任务获取订阅源频道
                    task = asyncio.create_task(
                        task_func(subscribe_urls,
                                  names=channel_names,
                                  whitelist=whitelist_urls,
                                  callback=self.update_progress
                                  )
                    )
                elif setting == "hotel_foodie" or setting == "hotel_fofa":
                    # 创建异步任务获取酒店相关频道
                    task = asyncio.create_task(task_func(callback=self.update_progress))
                else:
                    # 创建异步任务获取其他类型频道
                    task = asyncio.create_task(
                        task_func(channel_names, callback=self.update_progress)
                    )
                self.tasks.append(task)
                # 等待任务完成并存储结果
                setattr(self, result_attr, await task)

    def pbar_update(self, name: str = "", item_name: str = ""):
        """更新进度条和进度回调"""
        if self.pbar.n < self.total:
            self.pbar.update()
            self.update_progress(
                f"正在进行{name}, 剩余{self.total - self.pbar.n}个{item_name}, 预计剩余时间: {get_pbar_remaining(n=self.pbar.n, total=self.total, start_time=self.start_time)}",
                int((self.pbar.n / self.total) * 100),
            )

    async def main(self):
        """主更新流程"""
        try:
            user_final_file = config.final_file
            main_start_time = time()
            
            # 如果启用更新功能
            if config.open_update:
                # 获取频道项目
                self.channel_items = get_channel_items()
                channel_names = [
                    name
                    for channel_obj in self.channel_items.values()
                    for name in channel_obj.keys()
                ]
                if not channel_names:
                    print(f"❌ No channel names found! Please check the {config.source_file}!")
                    return
                
                # 访问并获取所有频道源数据
                await self.visit_page(channel_names)
                self.tasks = []
                
                # 合并所有来源的频道数据
                append_total_data(
                    self.channel_items.items(),
                    self.channel_data,
                    self.hotel_fofa_result,
                    self.multicast_result,
                    self.hotel_foodie_result,
                    self.subscribe_result,
                    self.online_search_result,
                )
                
                # 检查IPv6支持情况
                ipv6_support = config.ipv6_support or check_ipv6_support()
                cache_result = self.channel_data
                test_result = {}
                
                # 如果启用测速功能
                if config.open_speed_test:
                    urls_total = get_urls_len(self.channel_data)
                    test_data = copy.deepcopy(self.channel_data)
                    # 处理嵌套字典，过滤不需要测速的主机
                    process_nested_dict(
                        test_data,
                        seen=set(),
                        filter_host=config.speed_test_filter_host,
                        ipv6_support=ipv6_support
                    )
                    self.total = get_urls_len(test_data)
                    print(f"Total urls: {urls_total}, need to test speed: {self.total}")
                    self.update_progress(
                        f"正在进行测速, 共{urls_total}个接口, {self.total}个接口需要进行测速",
                        0,
                    )
                    self.start_time = time()
                    self.pbar = tqdm(total=self.total, desc="Speed test")
                    # 异步测试所有频道的速度
                    test_result = await test_speed(
                        test_data,
                        ipv6=ipv6_support,
                        callback=lambda: self.pbar_update(name="测速", item_name="接口"),
                    )
                    self.pbar.close()
                    # 合并测速结果
                    cache_result = merge_objects(cache_result, test_result, match_key="url")
                
                # 对频道结果进行排序
                self.channel_data = sort_channel_result(
                    self.channel_data,
                    result=test_result,
                    filter_host=config.speed_test_filter_host,
                    ipv6_support=ipv6_support
                )
                
                self.update_progress(
                    f"正在生成结果文件",
                    0,
                )
                # 将频道数据写入文件
                write_channel_to_file(
                    self.channel_data,
                    epg=self.epg_result,
                    ipv6=ipv6_support,
                    first_channel_name=channel_names[0],
                )
                
                # 如果启用历史记录功能
                if config.open_history:
                    if os.path.exists(constants.cache_path):
                        with gzip.open(constants.cache_path, "rb") as file:
                            try:
                                cache = pickle.load(file)
                            except EOFError:
                                cache = {}
                            # 合并历史记录和当前结果
                            cache_result = merge_objects(cache, cache_result, match_key="url")
                    with gzip.open(constants.cache_path, "wb") as file:
                        pickle.dump(cache_result, file)
                
                print(
                    f"🥳 Update completed! Total time spent: {format_interval(time() - main_start_time)}. Please check the {user_final_file} file!"
                )
            
            # 如果运行在UI模式下
            if self.run_ui:
                open_service = config.open_service
                service_tip = ", 可使用以下地址进行观看:" if open_service else ""
                tip = (
                    f"✅ 服务启动成功{service_tip}"
                    if open_service and config.open_update == False
                    else f"🥳 更新完成, 耗时: {format_interval(time() - main_start_time)}, 请检查{user_final_file}文件{service_tip}"
                )
                self.update_progress(
                    tip,
                    100,
                    True,
                    url=f"{get_ip_address()}" if open_service else None,
                )
        except asyncio.exceptions.CancelledError:
            print("Update cancelled!")

    async def start(self, callback=None):
        """启动更新流程，可传入进度回调函数"""
        def default_callback(*args, **kwargs):
            pass

        self.update_progress = callback or default_callback
        self.run_ui = True if callback else False
        await self.main()

    def stop(self):
        """停止所有正在运行的更新任务"""
        for task in self.tasks:
            task.cancel()
        self.tasks = []
        if self.pbar:
            self.pbar.close()


if __name__ == "__main__":
    # 程序入口点
    info = get_version_info()
    print(f"ℹ️ {info['name']} Version: {info['version']}")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    update_source = UpdateSource()
    loop.run_until_complete(update_source.start())
