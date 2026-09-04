import os
import sys
import json
import re
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

def find_json_match(filename, json_map):
    f_lower = filename.lower()
    stem, ext = os.path.splitext(filename)
    
    cands = [
        f_lower + '.supplemental-metadata.json',
        f_lower + '.json',
        stem.lower() + '.supplemental-metadata.json',
    ]
    
    if '(' in filename:
        m = re.search(r'\((\d+)\)', filename)
        if m:
            num = m.group(0)
            cands.append(f'{stem}.supplemental-metadata({num}).json')
            
    for c in cands:
        if c.lower() in json_map:
            return json_map[c.lower()]
    return None

def parse_json(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return int(data.get('photoTakenTime', {}).get('timestamp', 0))

def run(target_dir):
    for root, dirs, files in os.walk(target_dir):
        json_map = {f.lower(): f for f in files if f.lower().endswith('.json')}
        for f in files:
            if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                matched = find_json_match(f, json_map)
                if matched:
                    ts = parse_json(os.path.join(root, matched))
                    if ts:
                        dt = datetime.fromtimestamp(ts).strftime('%Y:%m:%d %H:%M:%S')
                        img_path = os.path.join(root, f)
                        subprocess.run(['exiftool', '-overwrite_original', f'-AllDates={dt}', img_path])
                        set_file_times(img_path, ts)

if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else '.')
