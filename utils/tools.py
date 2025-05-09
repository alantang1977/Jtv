import os
import re
import json
import logging
import shutil
import sys
import time
import asyncio
import pytz
import requests
from bs4 import BeautifulSoup
from flask import send_file, make_response
from opencc import OpenCC

import utils.constants as constants
from utils.config import config
from utils.types import ChannelData

opencc_t2s = OpenCC("t2s")

def convert_to_m3u(path=None, first_channel_name=None, data=None, epg_data=None):
    """
    将频道数据转换为标准M3U播放列表格式
    
    Args:
        path: 输出文件路径
        first_channel_name: 第一个频道名称（可选）
        data: 频道数据字典 {category: {channel_name: [{url, logo, ...}]}}
        epg_data: EPG数据字典，用于关联频道ID和图标
    """
    if not path or not data:
        logging.error("M3U生成失败：缺少路径或数据")
        return
    
    try:
        # 确保目录存在
        os.makedirs(os.path.dirname(path), exist_ok=True)
        
        with open(path, 'w', encoding='utf-8') as file:
            # 写入M3U头部
            file.write("#EXTM3U x-tvg-url=\"\"\n")
            
            # 遍历每个分类
            for category, channels in data.items():
                # 遍历分类下的每个频道
                for name, infos in channels.items():
                    # 遍历频道的每个源
                    for i, info in enumerate(infos):
                        url = info.get('url', '')
                        if not url:
                            continue
                            
                        # 获取频道Logo
                        logo = info.get('logo', '')
                        
                        # 获取或生成频道ID
                        channel_id = info.get('tvg-id', f"{name.replace(' ', '_')}_{i}")
                        
                        # 获取频道组
                        group_title = info.get('group-title', category)
                        
                        # 构建EXTINF行
                        extinf = f"#EXTINF:-1 "
                        if channel_id:
                            extinf += f"tvg-id=\"{channel_id}\" "
                        if name:
                            extinf += f"tvg-name=\"{name}\" "
                        if logo:
                            extinf += f"tvg-logo=\"{logo}\" "
                        if group_title:
                            extinf += f"group-title=\"{group_title}\" "
                            
                        # 添加其他可能的M3U属性
                        for key, value in info.items():
                            if key.startswith('tvg-') or key in ['catchup-days', 'catchup-type', 'catchup', 'radio']:
                                extinf += f"{key}=\"{value}\" "
                        
                        # 添加频道名称
                        extinf += f",{name}\n"
                        
                        # 写入EXTINF行和URL
                        file.write(extinf)
                        file.write(f"{url}\n")
                        
        logging.info(f"✅ M3U文件已生成: {path}")
        return True
    except Exception as e:
        logging.error(f"❌ 生成M3U文件时出错: {str(e)}")
        return False
