# tkinter_ui/default.py - 默认设置UI
import os
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox, ttk

import utils.constants as constants
from utils.config import config
from utils.tools import resource_path


class DefaultUI:
    """默认设置UI"""
    
    def init_ui(self, root):
        """初始化默认UI"""
        # 主框架
        frame_default = tk.LabelFrame(root, text="默认设置")
        frame_default.pack(fill=tk.X, padx=10, pady=10)
        
        # 开启服务
        frame_open_service = tk.Frame(frame_default)
        frame_open_service.pack(fill=tk.X, padx=5, pady=5)
        
        self.open_service_label = tk.Label(
            frame_open_service, text="开启服务:", width=15
        )
        self.open_service_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.open_service_var = tk.BooleanVar(value=config.open_service)
        self.open_service_checkbutton = ttk.Checkbutton(
            frame_open_service,
            variable=self.open_service_var,
            onvalue=True,
            offvalue=False,
            command=self.update_open_service,
        )
        self.open_service_checkbutton.pack(side=tk.LEFT, padx=4, pady=8)
        
        # 开启自动更新
        frame_open_update = tk.Frame(frame_default)
        frame_open_update.pack(fill=tk.X, padx=5, pady=5)
        
        self.open_update_label = tk.Label(
            frame_open_update, text="开启自动更新:", width=15
        )
        self.open_update_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.open_update_var = tk.BooleanVar(value=config.open_update)
        self.open_update_checkbutton = ttk.Checkbutton(
            frame_open_update,
            variable=self.open_update_var,
            onvalue=True,
            offvalue=False,
            command=self.update_open_update,
        )
        self.open_update_checkbutton.pack(side=tk.LEFT, padx=4, pady=8)
        
        # 服务端口
        frame_app_port = tk.Frame(frame_default)
        frame_app_port.pack(fill=tk.X, padx=5, pady=5)
        
        self.app_port_label = tk.Label(
            frame_app_port, text="服务端口:", width=15
        )
        self.app_port_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.app_port_var = tk.StringVar(value=str(config.app_port))
        self.app_port_entry = ttk.Entry(
            frame_app_port, textvariable=self.app_port_var, width=10
        )
        self.app_port_entry.pack(side=tk.LEFT, padx=4, pady=8)
        self.app_port_entry.bind("<FocusOut>", self.update_app_port)
        
        # 时区设置
        frame_time_zone = tk.Frame(frame_default)
        frame_time_zone.pack(fill=tk.X, padx=5, pady=5)
        
        self.time_zone_label = tk.Label(
            frame_time_zone, text="时区:", width=15
        )
        self.time_zone_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.time_zone_var = tk.StringVar(value=config.time_zone)
        self.time_zone_combobox = ttk.Combobox(
            frame_time_zone, textvariable=self.time_zone_var, width=20
        )
        self.time_zone_combobox['values'] = pytz.all_timezones
        self.time_zone_combobox.pack(side=tk.LEFT, padx=4, pady=8)
        self.time_zone_combobox.bind("<<ComboboxSelected>>", self.update_time_zone)
        
        # M3U特定设置
        frame_m3u = tk.LabelFrame(frame_default, text="M3U设置")
        frame_m3u.pack(fill=tk.X, padx=5, pady=5)
        
        # 包含EPG信息
        frame_m3u_epg = tk.Frame(frame_m3u)
        frame_m3u_epg.pack(fill=tk.X, padx=5, pady=5)
        
        self.m3u_epg_label = tk.Label(
            frame_m3u_epg, text="包含EPG信息:", width=15
        )
        self.m3u_epg_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.m3u_epg_var = tk.BooleanVar(value=config.open_method.get("epg", True))
        self.m3u_epg_checkbutton = ttk.Checkbutton(
            frame_m3u_epg,
            variable=self.m3u_epg_var,
            onvalue=True,
            offvalue=False,
            command=self.update_m3u_epg,
        )
        self.m3u_epg_checkbutton.pack(side=tk.LEFT, padx=4, pady=8)
        
        # 自动打开M3U结果
        frame_open_m3u = tk.Frame(frame_m3u)
        frame_open_m3u.pack(fill=tk.X, padx=5, pady=5)
        
        self.open_m3u_label = tk.Label(
            frame_open_m3u, text="生成后自动打开:", width=15
        )
        self.open_m3u_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.open_m3u_var = tk.BooleanVar(value=config.open_m3u_result)
        self.open_m3u_checkbutton = ttk.Checkbutton(
            frame_open_m3u,
            variable=self.open_m3u_var,
            onvalue=True,
            offvalue=False,
            command=self.update_open_m3u,
        )
        self.open_m3u_checkbutton.pack(side=tk.LEFT, padx=4, pady=8)
    
    def update_open_update(self):
        """更新开启自动更新设置"""
        config.set("Settings", "open_update", str(self.open_update_var.get()))
    
    def update_open_service(self):
        """更新开启服务设置"""
        config.set("Settings", "open_service", str(self.open_service_var.get()))
    
    def update_app_port(self, event):
        """更新服务端口设置"""
        try:
            port = int(self.app_port_var.get())
            if 1 <= port <= 65535:
                config.set("Settings", "app_port", str(port))
            else:
                messagebox.showerror("错误", "端口号必须在1-65535之间")
                self.app_port_var.set(str(config.app_port))
        except ValueError:
            messagebox.showerror("错误", "请输入有效的端口号")
            self.app_port_var.set(str(config.app_port))
    
    def update_time_zone(self, event):
        """更新时区设置"""
        config.set("Settings", "time_zone", self.time_zone_var.get())
    
    def update_m3u_epg(self):
        """更新M3U包含EPG信息设置"""
        config.set("Methods", "open_epg", str(self.m3u_epg_var.get()))
    
    def update_open_m3u(self):
        """更新生成后自动打开M3U设置"""
        config.set("Settings", "open_m3u_result", str(self.open_m3u_var.get()))
