import configparser
import os

class Config:
    def __init__(self):
        self.config = configparser.ConfigParser()
        self.config.read('config/config.ini')

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
