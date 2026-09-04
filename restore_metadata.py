import os
import sys
import json
import re
import time
import shutil
import ctypes
import tempfile
import subprocess
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from ctypes import wintypes

MEDIA_EXTS = {
    '.jpg', '.jpeg', '.png', '.heic', '.heif', '.webp',
    '.gif', '.mp4', '.mov', '.mkv', '.svg', '.mp', '.m4v'
}

VIDEO_EXTS = {'.mp4', '.mov', '.mkv', '.m4v'}

def get_exiftool():
    p = shutil.which("exiftool")
    if p:
        return p
    local_app = os.environ.get("LOCALAPPDATA", "")
    candidates = [
        os.path.join(local_app, r"Programs\ExifTool\ExifTool.exe"),
        r"C:\Program Files\ExifTool\exiftool.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "exiftool"

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
                f'{c_stem}({num}){c_ext}.supplemental-metadata.json',
                f'{stem_lower}.supplemental-metadata({num}).json',
            ])
            
    for c in cands:
        if c.lower() in json_map:
            return json_map[c.lower()]
            
    for j_lower, j_orig in json_map.items():
        if j_lower.startswith(stem_lower[:45]) and ('metadata' in j_lower or 'json' in j_lower):
            return j_orig
            
    return None

def parse_json(item):
    media_path, json_path = item
    try:
        with open(json_path, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
        ts = int(data.get('photoTakenTime', {}).get('timestamp', 0))
        geo = data.get('geoData', {})
        lat = geo.get('latitude', 0.0)
        lng = geo.get('longitude', 0.0)
        alt = geo.get('altitude', 0.0)
        return {
            'media_path': media_path,
            'timestamp': ts,
            'has_gps': (lat != 0.0 or lng != 0.0),
            'latitude': lat,
            'longitude': lng,
            'altitude': alt,
            'description': data.get('description', '').strip()
        }
    except Exception:
        return None

def run(target_dir, batch_size=1000):
    exiftool = get_exiftool()
    pairs = []
    for root, dirs, files in os.walk(target_dir):
        json_map = {f.lower(): f for f in files if f.lower().endswith('.json')}
        for f in files:
            if os.path.splitext(f)[1].lower() in MEDIA_EXTS:
                matched = find_json_match(f, json_map)
                if matched:
                    pairs.append((os.path.join(root, f), os.path.join(root, matched)))
                    
    with ThreadPoolExecutor(max_workers=32) as pool:
        parsed = [p for p in pool.map(parse_json, pairs) if p and p['timestamp']]
        
    batches = [parsed[i:i + batch_size] for i in range(0, len(parsed), batch_size)]
    for idx, batch in enumerate(batches, 1):
        lines = []
        for item in batch:
            media = item['media_path']
            d_str = datetime.fromtimestamp(item['timestamp']).strftime('%Y:%m:%d %H:%M:%S')
            is_vid = os.path.splitext(media)[1].lower() in VIDEO_EXTS
            lines.extend(["-overwrite_original", "-charset", "filename=utf8", "-charset", "utf8"])
            if is_vid:
                lines.extend(["-api", "QuickTimeUTC=1", f"-QuickTime:CreateDate={d_str}", f"-QuickTime:ModifyDate={d_str}", f"-Keys:CreationDate={d_str}"])
            else:
                lines.extend([f"-AllDates={d_str}"])
            lines.extend([media, "-execute"])
            
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, suffix='.txt') as tmp:
            for l in lines:
                tmp.write(l + "\n")
            tmp_name = tmp.name
        try:
            subprocess.run([exiftool, "-@", tmp_name], capture_output=True, text=True)
        finally:
            try:
                os.remove(tmp_name)
            except Exception:
                pass
        for item in batch:
            set_file_times(item['media_path'], item['timestamp'])
        print(f"batch {idx}/{len(batches)} done")

if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else '.')
