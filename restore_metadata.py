import os
import sys
import json
import ctypes
import subprocess
from datetime import datetime
from ctypes import wintypes

def set_file_times(filepath, timestamp):
    try:
        w_time = int((timestamp + 11644473600) * 10000000)
        low = w_time & 0xFFFFFFFF
        high = (w_time >> 32) & 0xFFFFFFFF
        filetime = wintypes.FILETIME(low, high)
        
        handle = ctypes.windll.kernel32.CreateFileW(
            filepath,
            0x40000000,
            0x00000001 | 0x00000002,
            None,
            3,
            0x00000080,
            None
        )
        if handle != -1 and handle != 0xFFFFFFFF:
            ctypes.windll.kernel32.SetFileTime(handle, ctypes.byref(filetime), ctypes.byref(filetime), ctypes.byref(filetime))
            ctypes.windll.kernel32.CloseHandle(handle)
    except Exception:
        pass
    try:
        os.utime(filepath, (timestamp, timestamp))
    except Exception:
        pass

def parse_json(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return int(data['photoTakenTime']['timestamp'])

def run(target_dir):
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f.endswith('.jpg'):
                json_file = os.path.join(root, f + '.supplemental-metadata.json')
                if not os.path.exists(json_file):
                    json_file = os.path.join(root, f + '.json')
                if os.path.exists(json_file):
                    ts = parse_json(json_file)
                    dt = datetime.fromtimestamp(ts).strftime('%Y:%m:%d %H:%M:%S')
                    img_path = os.path.join(root, f)
                    subprocess.run(['exiftool', '-overwrite_original', f'-AllDates={dt}', img_path])
                    set_file_times(img_path, ts)

if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else '.')
