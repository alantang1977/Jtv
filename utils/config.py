import configparser
import os
import sys

class Config:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config/config.ini')
        
        # 创建默认配置（如果不存在）
        self._create_default_config()
    
    def _create_default_config(self):
        """创建默认配置项（如果不存在）"""
        if not self.config.has_section("Settings"):
            self.config.add_section("Settings")
        
        # 添加或更新必要的配置项
        settings = {
            "source_file": "config/demo.txt",
            "final_file": "output/result.m3u",
            "open_update": "True",
            "open_speed_test": "True",
            "open_history": "True",
            "open_service": "False",
            "open_hotel": "False",
            "open_m3u_result": "True",
            "ipv6_support": "False",
            "speed_test_filter_host": "False",
            "cdn_url": "",
            "location": "",
            "isp": "",
            "app_port": "8080",
            "time_zone": "Asia/Shanghai"
        }
        
        for key, value in settings.items():
            if not self.config.has_option("Settings", key):
                self.config.set("Settings", key, value)
        
        self.save()
    
    def save(self):
        """保存配置到文件"""
        with open('config/config.ini', 'w', encoding='utf-8') as f:
            self.config.write(f)
    
    def set(self, section, option, value):
        """设置配置值"""
        if not self.config.has_section(section):
            self.config.add_section(section)
        self.config.set(section, option, value)
        self.save()
    
    @property
    def source_file(self):
        return self.config.get("Settings", "source_file", fallback="config/demo.txt")

    @property
    def final_file(self):
        return self.config.get("Settings", "final_file", fallback="output/result.m3u")

    @property
    def open_update(self):
        return self.config.getboolean("Settings", "open_update", fallback=True)

    @property
    def open_speed_test(self):
        return self.config.getboolean("Settings", "open_speed_test", fallback=True)

    @property
    def open_history(self):
        return self.config.getboolean("Settings", "open_history", fallback=True)

    @property
    def open_service(self):
        return self.config.getboolean("Settings", "open_service", fallback=False)

    @property
    def open_hotel(self):
        return self.config.getboolean("Settings", "open_hotel", fallback=False)

    @property
    def open_m3u_result(self):
        return self.config.getboolean("Settings", "open_m3u_result", fallback=True)

    @property
    def ipv6_support(self):
        return self.config.getboolean("Settings", "ipv6_support", fallback=False)

    @property
    def speed_test_filter_host(self):
        return self.config.getboolean("Settings", "speed_test_filter_host", fallback=False)

    @property
    def cdn_url(self):
        return self.config.get("Settings", "cdn_url", fallback=None)

    @property
    def location(self):
        return self.config.get("Settings", "location", fallback="").split(',')

    @property
    def isp(self):
        return self.config.get("Settings", "isp", fallback="").split(',')

    @property
    def open_method(self):
        return {
            "hotel_fofa": self.config.getboolean("Methods", "open_hotel_fofa", fallback=False),
            "multicast": self.config.getboolean("Methods", "open_multicast", fallback=False),
            "hotel_foodie": self.config.getboolean("Methods", "open_hotel_foodie", fallback=False),
            "subscribe": self.config.getboolean("Methods", "open_subscribe", fallback=True),
            "online_search": self.config.getboolean("Methods", "open_online_search", fallback=False),
            "epg": self.config.getboolean("Methods", "open_epg", fallback=True),
        }

    def resource_path(self, relative_path, persistent=False):
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

config = Config()
