import asyncio
import subprocess
import re

def get_speed(url, ipv6=False, callback=None):
    """
    测试URL的速度
    """
    try:
        command = ['ffmpeg', '-i', url, '-t', '5', '-f', 'null', '-']
        if ipv6:
            command.insert(1, '-6')
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        output = result.stderr
        speed_match = re.search(r'bitrate: (\d+) kb/s', output)
        resolution_match = re.search(r'(\d+)x(\d+)', output)
        speed = int(speed_match.group(1)) if speed_match else None
        resolution = resolution_match.group(0) if resolution_match else None
        if callback:
            callback()
        return {
            'url': url,
            'speed': speed,
            'resolution': resolution
        }
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return {
            'url': url,
            'speed': None,
            'resolution': None
        }


def get_speed_result(data, ipv6=False, callback=None):
    """
    获取所有URL的速度测试结果
    """
    tasks = []
    for category, channels in data.items():
        for name, infos in channels.items():
            for info in infos:
                url = info['url']
                task = asyncio.create_task(get_speed(url, ipv6=ipv6, callback=callback))
                tasks.append(task)
    return asyncio.gather(*tasks)


def get_sort_result(data, result):
    """
    根据速度测试结果对数据进行排序
    """
    sorted_data = {}
    for category, channels in data.items():
        sorted_data[category] = {}
        for name, infos in channels.items():
            sorted_infos = []
            for info in infos:
                url = info['url']
                for res in result:
                    if res['url'] == url:
                        info['speed'] = res['speed']
                        info['resolution'] = res['resolution']
                        sorted_infos.append(info)
                        break
            sorted_infos.sort(key=lambda x: x.get('speed', float('inf')))
            sorted_data[category][name] = sorted_infos
    return sorted_data


def check_ffmpeg_installed_status():
    """
    检查FFmpeg是否安装
    """
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True)
        return True
    except FileNotFoundError:
        return False
