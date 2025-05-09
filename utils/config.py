import configparser
import os

class Config:
    """配置管理类，负责读取和管理应用配置"""
    
    def __init__(self):
        """初始化配置管理器"""
        self.config = configparser.ConfigParser()
        self.config.read('config/config.ini')

    @property
    def source_file(self):
        """获取源文件路径"""
        return self.config.get("Settings", "source_file", fallback="config/demo.txt")

    @property
    def final_file(self):
        """获取最终输出文件路径"""
        return self.config.get("Settings", "final_file", fallback="output/result.m3u")

    @property
    def open_update(self):
        """是否启用自动更新"""
        return self.config.getboolean("Settings", "open_update", fallback=True)

    @property
    def open_speed_test(self):
        """是否启用测速功能"""
        return self.config.getboolean("Settings", "open_speed_test", fallback=True)

    @property
    def open_history(self):
        """是否启用历史记录功能"""
        return self.config.getboolean("Settings", "open_history", fallback=True)

    @property
    def open_service(self):
        """是否启用服务"""
        return self.config.getboolean("Settings", "open_service", fallback=False)

    @property
    def open_hotel(self):
        """是否启用酒店相关数据源"""
        return self.config.getboolean("Settings", "open_hotel", fallback=False)

    @property
    def open_m3u_result(self):
        """是否启用M3U结果格式"""
        return self.config.getboolean("Settings", "open_m3u_result", fallback=True)

    @property
    def ipv6_support(self):
        """是否支持IPv6"""
        return self.config.getboolean("Settings", "ipv6_support", fallback=False)

    @property
    def speed_test_filter_host(self):
        """是否在测速时过滤重复主机"""
        return self.config.getboolean("Settings", "speed_test_filter_host", fallback=False)

    @property
    def cdn_url(self):
        """获取CDN URL配置"""
        return self.config.get("Settings", "cdn_url", fallback=None)

    @property
    def location(self):
        """获取位置配置"""
        return self.config.get("Settings", "location", fallback="").split(',')

    @property
    def isp(self):
        """获取ISP配置"""
        return self.config.get("Settings", "isp", fallback="").split(',')

    @property
    def open_method(self):
        """获取各数据源的启用状态"""
        return {
            "hotel_fofa": self.config.getboolean("Methods", "open_hotel_fofa", fallback=False),
            "multicast": self.config.getboolean("Methods", "open_multicast", fallback=False),
            "hotel_foodie": self.config.getboolean("Methods", "open_hotel_foodie", fallback=False),
            "subscribe": self.config.getboolean("Methods", "open_subscribe", fallback=True),
            "online_search": self.config.getboolean("Methods", "open_online_search", fallback=False),
            "epg": self.config.getboolean("Methods", "open_epg", fallback=True),
        }

    def resource_path(self, relative_path, persistent=False):
        """获取资源路径，处理打包后的资源位置"""
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

# 创建全局配置实例
config = Config()
