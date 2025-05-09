import os
import configparser
from utils.tools import resource_path

class ConfigManager:
    """配置管理器，负责加载和管理应用配置"""
    
    def __init__(self):
        self.config = None
        self.load()

    def __getattr__(self, name, *args, **kwargs):
        return getattr(self.config, name, *args, **kwargs)

    @property
    def open_service(self):
        """是否开启服务"""
        return self.config.getboolean("Settings", "open_service", fallback=True)

    @property
    def open_update(self):
        """是否开启自动更新"""
        return self.config.getboolean("Settings", "open_update", fallback=True)

    @property
    def open_use_cache(self):
        """是否使用缓存"""
        return self.config.getboolean("Settings", "open_use_cache", fallback=True)

    @property
    def open_request(self):
        """是否开启网络请求"""
        return self.config.getboolean("Settings", "open_request", fallback=False)

    @property
    def open_filter_speed(self):
        """是否开启速度过滤"""
        return self.config.getboolean(
            "Settings", "open_filter_speed", fallback=True
        )

    @property
    def open_filter_resolution(self):
        """是否开启分辨率过滤"""
        return self.config.getboolean(
            "Settings", "open_filter_resolution", fallback=True
        )

    @property
    def ipv_type(self):
        """IP类型设置"""
        return self.config.get("Settings", "ipv_type", fallback="全部").lower()

    @property
    def open_ipv6(self):
        """是否支持IPv6"""
        return (
                "ipv6" in self.ipv_type or "all" in self.ipv_type or "全部" in self.ipv_type
        )

    @property
    def ipv_type_prefer(self):
        """IP类型偏好设置"""
        return [
            ipv_type_value.lower()
            for ipv_type in self.config.get(
                "Settings", "ipv_type_prefer", fallback=""
            ).split(",")
            if (ipv_type_value := ipv_type.strip())
        ]

    @property
    def ipv4_num(self):
        """IPv4数量限制"""
        try:
            return self.config.getint("Settings", "ipv4_num", fallback=5)
        except:
            return 5

    @property
    def ipv6_num(self):
        """IPv6数量限制"""
        try:
            return self.config.getint("Settings", "ipv6_num", fallback=5)
        except:
            return 5

    @property
    def ipv6_support(self):
        """是否强制支持IPv6"""
        return self.config.getboolean("Settings", "ipv6_support", fallback=False)

    @property
    def ipv_limit(self):
        """IP类型限制配置"""
        return {
            "all": self.urls_limit,
            "ipv4": self.ipv4_num,
            "ipv6": self.ipv6_num,
        }

    @property
    def origin_type_prefer(self):
        """数据源类型偏好"""
        return [
            origin_value.lower()
            for origin in self.config.get(
                "Settings",
                "origin_type_prefer",
                fallback="",
            ).split(",")
            if (origin_value := origin.strip())
        ]

    @property
    def hotel_num(self):
        """酒店源数量限制"""
        return self.config.getint("Settings", "hotel_num", fallback=10)

    @property
    def multicast_num(self):
        """组播源数量限制"""
        return self.config.getint("Settings", "multicast_num", fallback=10)

    @property
    def subscribe_num(self):
        """订阅源数量限制"""
        return self.config.getint("Settings", "subscribe_num", fallback=10)

    @property
    def online_search_num(self):
        """在线搜索数量限制"""
        return self.config.getint("Settings", "online_search_num", fallback=10)

    @property
    def source_limits(self):
        """各数据源限制配置"""
        return {
            "all": self.urls_limit,
            "local": self.local_num,
            "hotel": self.hotel_num,
            "multicast": self.multicast_num,
            "subscribe": self.subscribe_num,
            "online_search": self.online_search_num,
        }

    @property
    def min_speed(self):
        """最低速度要求(Mbps)"""
        return self.config.getfloat("Settings", "min_speed", fallback=0.5)

    @property
    def min_resolution(self):
        """最低分辨率要求"""
        return self.config.get("Settings", "min_resolution", fallback="1920x1080")

    @property
    def min_resolution_value(self):
        """最低分辨率数值表示"""
        return get_resolution_value(self.min_resolution)

    @property
    def max_resolution(self):
        """最高分辨率要求"""
        return self.config.get("Settings", "max_resolution", fallback="1920x1080")

    @property
    def max_resolution_value(self):
        """最高分辨率数值表示"""
        return get_resolution_value(self.max_resolution)

    @property
    def urls_limit(self):
        """总URL数量限制"""
        return self.config.getint("Settings", "urls_limit", fallback=30)

    @property
    def open_url_info(self):
        """是否显示URL信息"""
        return self.config.getboolean("Settings", "open_url_info", fallback=True)

    @property
    def recent_days(self):
        """最近天数限制"""
        return self.config.getint("Settings", "recent_days", fallback=30)

    @property
    def source_file(self):
        """源文件路径"""
        return self.config.get("Settings", "source_file", fallback="config/demo.txt")

    @property
    def final_file(self):
        """最终输出文件路径"""
        return self.config.get("Settings", "final_file", fallback="output/result.txt")

    @property
    def open_m3u_result(self):
        """是否生成M3U格式结果"""
        return self.config.getboolean("Settings", "open_m3u_result", fallback=True)

    @property
    def open_subscribe(self):
        """是否开启订阅源"""
        return self.config.getboolean("Settings", f"open_subscribe", fallback=True)

    @property
    def open_hotel(self):
        """是否开启酒店源"""
        return self.config.getboolean("Settings", f"open_hotel", fallback=True)

    @property
    def open_hotel_fofa(self):
        """是否开启酒店源Fofa搜索"""
        return self.config.getboolean("Settings", f"open_hotel_fofa", fallback=True)

    @property
    def open_hotel_foodie(self):
        """是否开启酒店源美食搜索"""
        return self.config.getboolean("Settings", f"open_hotel_foodie", fallback=True)

    @property
    def open_multicast(self):
        """是否开启组播源"""
        return self.config.getboolean("Settings", f"open_multicast", fallback=True)

    @property
    def open_multicast_fofa(self):
        """是否开启组播源Fofa搜索"""
        return self.config.getboolean("Settings", f"open_multicast_fofa", fallback=True)

    @property
    def open_multicast_foodie(self):
        """是否开启组播源美食搜索"""
        return self.config.getboolean(
            "Settings", f"open_multicast_foodie", fallback=True
        )

    @property
    def open_online_search(self):
        """是否开启在线搜索"""
        return self.config.getboolean("Settings", f"open_online_search", fallback=True)

    @property
    def open_method(self):
        """各种获取方法的开启状态"""
        return {
            "epg": self.open_epg,
            "local": self.open_local,
            "subscribe": self.open_subscribe,
            "hotel": self.open_hotel,
            "multicast": self.open_multicast,
            "online_search": self.open_online_search,
            "hotel_fofa": self.open_hotel and self.open_hotel_fofa,
            "hotel_foodie": self.open_hotel and self.open_hotel_foodie,
            "multicast_fofa": self.open_multicast and self.open_multicast_fofa,
            "multicast_foodie": self.open_multicast and self.open_multicast_foodie,
        }

    @property
    def open_history(self):
        """是否开启历史记录"""
        return self.config.getboolean("Settings", "open_history", fallback=True)

    @property
    def open_speed_test(self):
        """是否开启速度测试"""
        return self.config.getboolean("Settings", "open_speed_test", fallback=True)

    @property
    def open_update_time(self):
        """是否显示更新时间"""
        return self.config.getboolean("Settings", "open_update_time", fallback=True)

    @property
    def multicast_region_list(self):
        """组播源地区列表"""
        return [
            region.strip()
            for region in self.config.get(
                "Settings", "multicast_region_list", fallback="全部"
            ).split(",")
            if region.strip()
        ]

    @property
    def hotel_region_list(self):
        """酒店源地区列表"""
        return [
            region.strip()
            for region in self.config.get(
                "Settings", "hotel_region_list", fallback="全部"
            ).split(",")
            if region.strip()
        ]

    @property
    def request_timeout(self):
        """请求超时时间(秒)"""
        return self.config.getint("Settings", "request_timeout", fallback=10)

    @property
    def speed_test_timeout(self):
        """测速超时时间(秒)"""
        return self.config.getint("Settings", "speed_test_timeout", fallback=10)

    @property
    def open_driver(self):
        """是否开启浏览器驱动模式"""
        return self.config.getboolean(
            "Settings", "open_driver", fallback=False
        )

    @property
    def hotel_page_num(self):
        """酒店源搜索页数"""
        return self.config.getint("Settings", "hotel_page_num", fallback=1)

    @property
    def multicast_page_num(self):
        """组播源搜索页数"""
        return self.config.getint("Settings", "multicast_page_num", fallback=1)

    @property
    def online_search_page_num(self):
        """在线搜索页数"""
        return self.config.getint("Settings", "online_search_page_num", fallback=1)

    @property
    def open_empty_category(self):
        """是否保留空分类"""
        return self.config.getboolean("Settings", "open_empty_category", fallback=True)

    @property
    def app_host(self):
        """应用主机地址"""
        return os.getenv("APP_HOST") or self.config.get("Settings", "app_host", fallback="http://localhost")

    @property
    def app_port(self):
        """应用端口"""
        return os.getenv("APP_PORT") or self.config.getint("Settings", "app_port", fallback=8000)

    @property
    def open_supply(self):
        """是否开启补偿机制"""
        return self.config.getboolean("Settings", "open_supply", fallback=True)

    @property
    def update_time_position(self):
        """更新时间位置"""
        return self.config.get("Settings", "update_time_position", fallback="top")

    @property
    def time_zone(self):
        """时区设置"""
        return self.config.get("Settings", "time_zone", fallback="Asia/Shanghai")

    @property
    def open_local(self):
        """是否开启本地源"""
        return self.config.getboolean("Settings", "open_local", fallback=True)

    @property
    def local_file(self):
        """本地源文件路径"""
        return self.config.get("Settings", "local_file", fallback="config/local.txt")

    @property
    def local_num(self):
        """本地源数量限制"""
        return self.config.getint("Settings", "local_num", fallback=10)

    @property
    def speed_test_filter_host(self):
        """是否按主机过滤测速结果"""
        return self.config.getboolean("Settings", "speed_test_filter_host", fallback=False)

    @property
    def cdn_url(self):
        """CDN地址"""
        return self.config.get("Settings", "cdn_url", fallback="")

    @property
    def open_rtmp(self):
        """是否开启RTMP"""
        return not os.getenv("GITHUB_ACTIONS") and self.config.getboolean("Settings", "open_rtmp", fallback=True)

    @property
    def open_headers(self):
        """是否开启请求头"""
        return self.config.getboolean("Settings", "open_headers", fallback=False)

    @property
    def open_epg(self):
        """是否开启EPG"""
        return self.config.getboolean("Settings", "open_epg", fallback=True)

    @property
    def speed_test_limit(self):
        """测速数量限制"""
        return self.config.getint("Settings", "speed_test_limit", fallback=10)

    @property
    def location(self):
        """位置设置"""
        return [
            l.strip()
            for l in self.config.get(
                "Settings", "location", fallback=""
            ).split(",")
            if l.strip()
        ]

    @property
    def isp(self):
        """ISP设置"""
        return [
            i.strip()
            for i in self.config.get(
                "Settings", "isp", fallback=""
            ).split(",")
            if i.strip()
        ]

    def load(self):
        """加载配置文件"""
        self.config = configparser.ConfigParser()
        user_config_path = resource_path("config/user_config.ini")
        default_config_path = resource_path("config/config.ini")

        # 用户配置会覆盖默认配置
        config_files = [default_config_path, user_config_path]
        for config_file in config_files:
            if os.path.exists(config_file):
                with open(config_file, "r", encoding="utf-8") as f:
                    self.config.read_file(f)

    def set(self, section, key, value):
        """设置配置项"""
        self.config.set(section, key, value)

    def save(self):
        """保存配置到文件"""
        user_config_file = "config/" + (
            "user_config.ini"
            if os.path.exists(resource_path("config/user_config.ini"))
            else "config.ini"
        )
        user_config_path = resource_path(user_config_file, persistent=True)
        if not os.path.exists(user_config_path):
            os.makedirs(os.path.dirname(user_config_path), exist_ok=True)
        with open(user_config_path, "w", encoding="utf-8") as configfile:
            self.config.write(configfile)

    def copy(self, path="config"):
        """复制配置文件到指定目录"""
        dest_folder = os.path.join(os.getcwd(), path)
        try:
            src_dir = resource_path(path)
            if os.path.exists(src_dir):
                if not os.path.exists(dest_folder):
                    os.makedirs(dest_folder, exist_ok=True)

                for root, _, files in os.walk(src_dir):
                    for file in files:
                        src_file_path = os.path.join(root, file)
                        relative_path = os.path.relpath(src_file_path, src_dir)
                        dest_file_path = os.path.join(dest_folder, relative_path)

                        dest_file_dir = os.path.dirname(dest_file_path)
                        if not os.path.exists(dest_file_dir):
                            os.makedirs(dest_file_dir, exist_ok=True)

                        if not os.path.exists(dest_file_path):
                            shutil.copy(src_file_path, dest_file_path)
        except Exception as e:
            print(f"Failed to copy files: {str(e)}")

# 创建全局配置实例
config = ConfigManager()
