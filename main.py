import os
import time
import asyncio
import pickle
import gzip
from collections import defaultdict
from tqdm import tqdm

import utils.constants as constants
from utils.config import config
from utils.tools import (
    convert_to_m3u,
    format_interval,
    get_pbar_remaining,
    get_urls_len,
    process_nested_dict,
    merge_objects,
    check_ipv6_support,
    sort_channel_result,
    write_channel_to_file,
    get_ip_address
)
from utils.channel import append_data_to_info_data

class UpdateSource:

    def __init__(self):
        self.update_progress = None
        self.run_ui = False
        self.tasks = []
        self.channel_items = defaultdict(dict)
        self.hotel_fofa_result = {}
        self.hotel_foodie_result = {}
        self.multicast_result = {}
        self.subscribe_result = {}
        self.online_search_result = {}
        self.epg_result = {}
        self.channel_data = defaultdict(dict)
        self.pbar = None
        self.total = 0
        self.start_time = None

    async def visit_page(self, channel_names: list[str] = None):
        tasks_config = [
            ("hotel_fofa", get_channels_by_fofa, "hotel_fofa_result"),
            ("multicast", get_channels_by_multicast, "multicast_result"),
            ("hotel_foodie", get_channels_by_hotel, "hotel_foodie_result"),
            ("subscribe", get_channels_by_subscribe_urls, "subscribe_result"),
            (
                "online_search",
                get_channels_by_online_search,
                "online_search_result",
            ),
            ("epg", get_epg, "epg_result"),
        ]

        for setting, task_func, result_attr in tasks_config:
            if (
                    setting == "hotel_foodie" or setting == "hotel_fofa"
            ) and config.open_hotel == False:
                continue
            if config.open_method[setting]:
                if setting == "subscribe":
                    subscribe_urls = get_urls_from_file(constants.subscribe_path)
                    whitelist_urls = get_urls_from_file(constants.whitelist_path)
                    if not os.getenv("GITHUB_ACTIONS") and config.cdn_url:
                        subscribe_urls = [join_url(config.cdn_url, url) if "raw.githubusercontent.com" in url else url
                                          for url in subscribe_urls]
                    task = asyncio.create_task(
                        task_func(subscribe_urls,
                                  names=channel_names,
                                  whitelist=whitelist_urls,
                                  callback=self.update_progress
                                  )
                    )
                elif setting == "hotel_foodie" or setting == "hotel_fofa":
                    task = asyncio.create_task(task_func(callback=self.update_progress))
                else:
                    task = asyncio.create_task(
                        task_func(channel_names, callback=self.update_progress)
                    )
                self.tasks.append(task)
                setattr(self, result_attr, await task)

    def pbar_update(self, name: str = "", item_name: str = ""):
        if self.pbar.n < self.total:
            self.pbar.update()
            self.update_progress(
                f"正在进行{name}, 剩余{self.total - self.pbar.n}个{item_name}, 预计剩余时间: {get_pbar_remaining(n=self.pbar.n, total=self.total, start_time=self.start_time)}",
                int((self.pbar.n / self.total) * 100),
            )

    async def main(self):
        try:
            user_final_file = config.final_file
            main_start_time = time()
            
            if config.open_update:
                self.channel_items = get_channel_items()
                channel_names = [
                    name
                    for channel_obj in self.channel_items.values()
                    for name in channel_obj.keys()
                ]
                if not channel_names:
                    print(f"❌ No channel names found! Please check the {config.source_file}!")
                    return
                
                await self.visit_page(channel_names)
                self.tasks = []
                
                append_total_data(
                    self.channel_items.items(),
                    self.channel_data,
                    self.hotel_fofa_result,
                    self.multicast_result,
                    self.hotel_foodie_result,
                    self.subscribe_result,
                    self.online_search_result,
                )
                
                ipv6_support = config.ipv6_support or check_ipv6_support()
                cache_result = self.channel_data
                test_result = {}
                
                if config.open_speed_test:
                    urls_total = get_urls_len(self.channel_data)
                    test_data = copy.deepcopy(self.channel_data)
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
                    test_result = await test_speed(
                        test_data,
                        ipv6=ipv6_support,
                        callback=lambda: self.pbar_update(name="测速", item_name="接口"),
                    )
                    cache_result = merge_objects(cache_result, test_result, match_key="url")
                    self.pbar.close()
                
                self.channel_data = sort_channel_result(
                    self.channel_data,
                    result=test_result,
                    filter_host=config.speed_test_filter_host,
                    ipv6_support=ipv6_support
                )
                
                self.update_progress(
                    f"正在生成M3U播放列表",
                    0,
                )
                
                # 生成M3U文件
                success = convert_to_m3u(
                    path=user_final_file,
                    first_channel_name=channel_names[0] if channel_names else None,
                    data=self.channel_data,
                    epg_data=self.epg_result if config.open_method.get("epg", True) else None
                )
                
                if not success:
                    print(f"❌ 生成M3U文件失败！")
                
                if config.open_history:
                    if os.path.exists(constants.cache_path):
                        with gzip.open(constants.cache_path, "rb") as file:
                            try:
                                cache = pickle.load(file)
                            except EOFError:
                                cache = {}
                            cache_result = merge_objects(cache, cache_result, match_key="url")
                    with gzip.open(constants.cache_path, "wb") as file:
                        pickle.dump(cache_result, file)
                
                print(
                    f"🥳 Update completed! Total time spent: {format_interval(time() - main_start_time)}. Please check the {user_final_file} file!"
                )
                
                # 自动打开M3U文件
                if config.open_m3u_result and success:
                    os.startfile(user_final_file)
            
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
        def default_callback(self, *args, **kwargs):
            pass

        self.update_progress = callback or default_callback
        self.run_ui = True if callback else False
        await self.main()

    def stop(self):
        for task in self.tasks:
            task.cancel()
        self.tasks = []
        if self.pbar:
            self.pbar.close()
