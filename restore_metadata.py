import os
import sys
import json
import re
import ctypes
import subprocess
from datetime import datetime
from ctypes import wintypes

VIDEO_EXTS = {'.mp4', '.mov', '.mkv', '.m4v'}
MEDIA_EXTS = {'.jpg', '.jpeg', '.png', '.heic', '.webp', '.gif', '.mp4', '.mov', '.mkv'}

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
    stem_lower = stem.lower()
    
    cands = [
        f_lower + '.supplemental-metadata.json',
        f_lower + '.json',
        stem_lower + '.supplemental-metadata.json',
        stem_lower + '.json',
    ]
    
    if '(' in filename and ')' in filename:
        m = re.search(r'\((\d+)\)', filename)
        if m:
            num = m.group(1)
            clean = re.sub(r'\s*\(\d+\)', '', filename).lower()
            c_stem, c_ext = os.path.splitext(clean)
            cands.extend([
                f'{clean}.supplemental-metadata({num}).json',
                f'{clean}.supplemental-metadata ({num}).json',
                f'{c_stem}{c_ext}.supplemental-metadata({num}).json',
                f'{c_stem}.supplemental-metadata({num}).json',
                f'{clean}({num}).json',
                f'{clean} ({num}).json',
                f'{stem_lower}.supplemental-metadata({num}).json',
                f'{f_lower}.supplemental-metadata({num}).json',
            ])
            
    for c in cands:
        if c.lower() in json_map:
            return json_map[c.lower()]
            
    for j_lower, j_orig in json_map.items():
        if j_lower.startswith(stem_lower[:45]) and ('metadata' in j_lower or 'json' in j_lower):
            return j_orig
            
    return None

def parse_json(json_path):
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        ts = int(data.get('photoTakenTime', {}).get('timestamp', 0))
        geo = data.get('geoData', {})
        lat = geo.get('latitude', 0.0)
        lng = geo.get('longitude', 0.0)
        alt = geo.get('altitude', 0.0)
        return {'ts': ts, 'lat': lat, 'lng': lng, 'alt': alt, 'desc': data.get('description', '')}
    except Exception:
        return None

def run(target_dir):
    for root, dirs, files in os.walk(target_dir):
        json_map = {f.lower(): f for f in files if f.lower().endswith('.json')}
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in MEDIA_EXTS:
                matched = find_json_match(f, json_map)
                if matched:
                    info = parse_json(os.path.join(root, matched))
                    if info and info['ts']:
                        dt = datetime.fromtimestamp(info['ts']).strftime('%Y:%m:%d %H:%M:%S')
                        file_path = os.path.join(root, f)
                        if ext in VIDEO_EXTS:
                            cmd = [
                                'exiftool', '-overwrite_original',
                                '-api', 'QuickTimeUTC=1',
                                f'-QuickTime:CreateDate={dt}',
                                f'-QuickTime:ModifyDate={dt}',
                                f'-Keys:CreationDate={dt}',
                                file_path
                            ]
                        else:
                            cmd = ['exiftool', '-overwrite_original', f'-AllDates={dt}', file_path]
                        subprocess.run(cmd)
                        set_file_times(file_path, info['ts'])

if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else '.')
