# Jtv/utils/constants.py
import os
from utils.config import config

# 确保项目根目录被添加到sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 文件路径配置
SOURCE_FILE = config.source_file
FINAL_FILE = config.final_file
CACHE_PATH = os.path.join(BASE_DIR, "cache", "channel_cache.gz")
SUBSCRIBE_PATH = os.path.join(BASE_DIR, "config", "subscribe.txt")
WHITELIST_PATH = os.path.join(BASE_DIR, "config", "whitelist.txt")
BLACKLIST_PATH = os.path.join(BASE_DIR, "config", "blacklist.txt")
USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"

# 其他常量
MAX_RETRIES = 3
TIMEOUT = 10
