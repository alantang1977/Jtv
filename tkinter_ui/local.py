# tkinter_ui/local.py - 本地源设置UI
import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from utils.config import config
from utils.tools import resource_path


class LocalUI:
    """本地源设置UI"""
    
    def init_ui(self, root):
        """初始化本地UI"""
        # 本地源框架
        frame_local = tk.LabelFrame(root, text="本地源设置")
        frame_local.pack(fill=tk.X, padx=10, pady=10)
        
        # 开启本地源
        frame_local_open_local = tk.Frame(frame_local)
        frame_local_open_local.pack(fill=tk.X, padx=5, pady=5)
        
        self.open_local_label = tk.Label(
            frame_local_open_local, text="开启本地源:", width=15
        )
        self.open_local_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.open_local_var = tk.BooleanVar(value=config.open_local)
        self.open_local_checkbutton = ttk.Checkbutton(
            frame_local_open_local,
            variable=self.open_local_var,
            onvalue=True,
            offvalue=False,
            command=self.update_open_local,
        )
        self.open_local_checkbutton.pack(side=tk.LEFT, padx=4, pady=8)
        
        # 本地源文件
        frame_local_file = tk.Frame(frame_local)
        frame_local_file.pack(fill=tk.X, padx=5, pady=5)
        
        self.local_file_label = tk.Label(
            frame_local_file, text="本地源文件:", width=15
        )
        self.local_file_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.local_file_var = tk.StringVar(value=config.local_file)
        self.local_file_entry = ttk.Entry(
            frame_local_file, textvariable=self.local_file_var, width=40
        )
        self.local_file_entry.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.local_file_button = tk.ttk.Button(
            frame_local_file,
            text="选择文件",
            command=self.select_local_file,
        )
        self.local_file_button.pack(side=tk.LEFT, padx=4, pady=0)
        
        self.local_file_edit_button = tk.ttk.Button(
            frame_local_file,
            text="编辑",
            command=self.edit_local_file,
        )
        self.local_file_edit_button.pack(side=tk.LEFT, padx=4, pady=0)
        
        # 本地源数量限制
        frame_local_num = tk.Frame(frame_local)
        frame_local_num.pack(fill=tk.X, padx=5, pady=5)
        
        self.local_num_label = tk.Label(
            frame_local_num, text="本地源数量限制:", width=15
        )
        self.local_num_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.local_num_var = tk.StringVar(value=str(config.local_num))
        self.local_num_spinbox = ttk.Spinbox(
            frame_local_num, from_=1, to=100, textvariable=self.local_num_var, width=5
        )
        self.local_num_spinbox.pack(side=tk.LEFT, padx=4, pady=8)
        self.local_num_spinbox.bind("<FocusOut>", self.update_local_num)
        
        # M3U特定设置
        frame_m3u_settings = tk.LabelFrame(frame_local, text="M3U设置")
        frame_m3u_settings.pack(fill=tk.X, padx=5, pady=5)
        
        # M3U输出路径
        frame_m3u_path = tk.Frame(frame_m3u_settings)
        frame_m3u_path.pack(fill=tk.X, padx=5, pady=5)
        
        self.m3u_path_label = tk.Label(
            frame_m3u_path, text="M3U输出路径:", width=15
        )
        self.m3u_path_label.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.m3u_path_var = tk.StringVar(value=config.final_file)
        self.m3u_path_entry = ttk.Entry(
            frame_m3u_path, textvariable=self.m3u_path_var, width=40
        )
        self.m3u_path_entry.pack(side=tk.LEFT, padx=4, pady=8)
        
        self.m3u_path_button = tk.ttk.Button(
            frame_m3u_path,
            text="选择路径",
            command=self.select_m3u_path,
        )
        self.m3u_path_button.pack(side=tk.LEFT, padx=4, pady=0)
    
    def update_open_local(self):
        """更新开启本地源设置"""
        config.set("Settings", "open_local", str(self.open_local_var.get()))
        self.change_entry_state("normal" if self.open_local_var.get() else "disabled")
    
    def select_local_file(self):
        """选择本地源文件"""
        filepath = filedialog.askopenfilename(
            initialdir=os.getcwd(), title="选择本地源文件", filetypes=[("文本文件", "*.txt")]
        )
        if filepath:
            self.local_file_var.set(filepath)
            config.set("Settings", "local_file", filepath)
    
    def edit_local_file(self):
        """编辑本地源文件"""
        path = self.local_file_var.get()
        real_path = resource_path(path)
        if os.path.exists(real_path):
            os.system(f'notepad.exe "{real_path}"')
        else:
            messagebox.showerror("错误", f"文件 {path} 不存在!")
    
    def update_local_num(self, event):
        """更新本地源数量限制"""
        try:
            num = int(self.local_num_var.get())
            if 1 <= num <= 100:
                config.set("Settings", "local_num", str(num))
            else:
                messagebox.showerror("错误", "数量必须在1-100之间")
                self.local_num_var.set(str(config.local_num))
        except ValueError:
            messagebox.showerror("错误", "请输入有效的数字")
            self.local_num_var.set(str(config.local_num))
    
    def select_m3u_path(self):
        """选择M3U输出路径"""
        filepath = filedialog.asksaveasfilename(
            initialdir=os.path.dirname(config.final_file),
            initialfile=os.path.basename(config.final_file),
            title="选择M3U输出路径",
            filetypes=[("M3U文件", "*.m3u"), ("所有文件", "*.*")]
        )
        if filepath:
            self.m3u_path_var.set(filepath)
            config.set("Settings", "final_file", filepath)
    
    def change_entry_state(self, state):
        """更改所有输入框状态"""
        for entry in [
            "local_file_entry",
            "local_file_button",
            "local_file_edit_button",
            "local_num_spinbox"
        ]:
            getattr(self, entry).config(state=state)
