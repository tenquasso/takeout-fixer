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
    prog_files = os.environ.get("ProgramFiles", "")
    candidates = [
        os.path.join(local_app, r"Programs\ExifTool\ExifTool.exe"),
        os.path.join(prog_files, r"ExifTool\exiftool.exe"),
        r"C:\Program Files\ExifTool\exiftool.exe",
        r"C:\Program Files (x86)\ExifTool\exiftool.exe",
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return "exiftool"

def set_file_times(filepath, timestamp):
    try:
        # windows filetime
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
            ctypes.windll.kernel32.SetFileTime(
                handle,
                ctypes.byref(filetime),
                ctypes.byref(filetime),
                ctypes.byref(filetime)
            )
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
    
    # handle takeout duplicate naming like (1)
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
                f'{c_stem} ({num}){c_ext}.supplemental-metadata.json',
                f'{stem_lower}.supplemental-metadata({num}).json',
                f'{f_lower}.supplemental-metadata({num}).json',
            ])
            
    if '-edited' in f_lower:
        unedited = f_lower.replace('-edited', '')
        u_stem, _ = os.path.splitext(unedited)
        cands.extend([
            unedited + '.supplemental-metadata.json',
            unedited + '.json',
            u_stem + '.supplemental-metadata.json',
            u_stem + '.json',
        ])
    
    for c in cands:
        if c.lower() in json_map:
            return json_map[c.lower()]
            
    # handle truncated names from takeout
    for j_lower, j_orig in json_map.items():
        if j_lower.startswith(stem_lower[:45]) and ('metadata' in j_lower or 'json' in j_lower):
            return j_orig
        elif j_lower.startswith(f_lower[:45]) and ('metadata' in j_lower or 'json' in j_lower):
            return j_orig
            
    return None

def parse_json(item):
    media_path, json_path = item
    try:
        with open(json_path, 'r', encoding='utf-8', errors='replace') as f:
            data = json.load(f)
            
        ts = None
        if 'photoTakenTime' in data and 'timestamp' in data['photoTakenTime']:
            try:
                ts = int(data['photoTakenTime']['timestamp'])
            except (ValueError, TypeError):
                pass
                
        if not ts and 'creationTime' in data and 'timestamp' in data['creationTime']:
            try:
                ts = int(data['creationTime']['timestamp'])
            except (ValueError, TypeError):
                pass
                
        desc = data.get('description', '').strip()
        geo = data.get('geoData', {})
        lat = geo.get('latitude', 0.0)
        lng = geo.get('longitude', 0.0)
        alt = geo.get('altitude', 0.0)
        has_gps = (lat != 0.0 or lng != 0.0)
        
        return {
            'media_path': media_path,
            'json_path': json_path,
            'timestamp': ts,
            'has_gps': has_gps,
            'latitude': lat,
            'longitude': lng,
            'altitude': alt,
            'description': desc,
        }
    except Exception:
        return None

def run(target_dir, backup_json=None, clean_json=False, dry_run=False, batch_size=1000):
    t0 = time.time()
    exiftool = get_exiftool()
    
    offset_str = datetime.now().astimezone().strftime('%z')
    tz_offset = f"{offset_str[:3]}:{offset_str[3:]}" if len(offset_str) == 5 else "+00:00"
    
    print(f"target: {target_dir}")
    print(f"timezone: {tz_offset}")
    
    pairs = []
    all_jsons = set()
    total_media = 0
    
    for root, dirs, files in os.walk(target_dir):
        # skip backup folder
        if backup_json and os.path.abspath(root).startswith(os.path.abspath(backup_json)):
            continue
            
        json_map = {f.lower(): f for f in files if f.lower().endswith('.json')}
        for j in json_map.values():
            all_jsons.add(os.path.join(root, j))
            
        for f in files:
            ext = os.path.splitext(f)[1].lower()
            if ext in MEDIA_EXTS:
                total_media += 1
                matched = find_json_match(f, json_map)
                if matched:
                    pairs.append((os.path.join(root, f), os.path.join(root, matched)))

    print(f"found {total_media} media files, matched {len(pairs)} with json ({len(pairs)/max(1, total_media)*100:.1f}%)")
    
    with ThreadPoolExecutor(max_workers=32) as pool:
        parsed = [p for p in pool.map(parse_json, pairs) if p and p['timestamp']]
        
    print(f"valid items to process: {len(parsed)}")
    
    if dry_run:
        print("dry run done.")
        return
        
    batches = [parsed[i:i + batch_size] for i in range(0, len(parsed), batch_size)]
    total_batches = len(batches)
    
    for idx, batch in enumerate(batches, 1):
        t_b = time.time()
        lines = []
        for item in batch:
            media = item['media_path']
            dt = datetime.fromtimestamp(item['timestamp'])
            d_str = dt.strftime('%Y:%m:%d %H:%M:%S')
            is_vid = os.path.splitext(media)[1].lower() in VIDEO_EXTS
            
            lines.extend([
                "-overwrite_original",
                "-charset", "filename=utf8",
                "-charset", "utf8",
            ])
            
            if is_vid:
                lines.extend([
                    "-api", "QuickTimeUTC=1",
                    f"-QuickTime:CreateDate={d_str}",
                    f"-QuickTime:ModifyDate={d_str}",
                    f"-QuickTime:TrackCreateDate={d_str}",
                    f"-QuickTime:MediaCreateDate={d_str}",
                    f"-Keys:CreationDate={d_str}{tz_offset}",
                ])
                if item['has_gps']:
                    lines.extend([
                        f"-Keys:GPSCoordinates={item['latitude']},{item['longitude']},{item['altitude']}",
                        f"-UserData:GPSCoordinates={item['latitude']},{item['longitude']},{item['altitude']}",
                    ])
                if item['description']:
                    lines.extend([
                        f"-QuickTime:Description={item['description']}",
                        f"-Keys:Description={item['description']}",
                    ])
            else:
                lines.extend([
                    f"-AllDates={d_str}",
                    f"-OffsetTime={tz_offset}",
                    f"-OffsetTimeOriginal={tz_offset}",
                    f"-OffsetTimeDigitized={tz_offset}",
                ])
                if item['has_gps']:
                    lat = item['latitude']
                    lng = item['longitude']
                    alt = item['altitude']
                    lines.extend([
                        f"-GPSLatitude={abs(lat)}",
                        f"-GPSLatitudeRef={'N' if lat >= 0 else 'S'}",
                        f"-GPSLongitude={abs(lng)}",
                        f"-GPSLongitudeRef={'E' if lng >= 0 else 'W'}",
                    ])
                    if alt != 0.0:
                        lines.extend([
                            f"-GPSAltitude={abs(alt)}",
                            f"-GPSAltitudeRef={0 if alt >= 0 else 1}",
                        ])
                if item['description']:
                    lines.extend([
                        f"-ImageDescription={item['description']}",
                        f"-Caption-Abstract={item['description']}",
                        f"-Description={item['description']}",
                    ])
            lines.extend([media, "-execute"])
            
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', delete=False, suffix='.txt') as tmp:
            tmp_name = tmp.name
            for line in lines:
                tmp.write(line + "\n")
            
        try:
            subprocess.run([exiftool, "-@", tmp_name], capture_output=True, text=True, encoding='utf-8', errors='replace')
        finally:
            try:
                os.remove(tmp_name)
            except Exception:
                pass
                
        for item in batch:
            set_file_times(item['media_path'], item['timestamp'])
            
        print(f"batch {idx}/{total_batches} done ({len(batch)} files) in {time.time() - t_b:.2f}s")
        
    if backup_json:
        print(f"moving json files to {backup_json}...")
        os.makedirs(backup_json, exist_ok=True)
        for j in all_jsons:
            try:
                rel = os.path.relpath(j, target_dir)
                dest = os.path.join(backup_json, rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.move(j, dest)
            except Exception:
                pass
        print("backup done.")
    elif clean_json:
        print("deleting json files...")
        for j in all_jsons:
            try:
                os.remove(j)
            except Exception:
                pass
        print("cleanup done.")
        
    print(f"all done in {time.time() - t0:.1f}s")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default=".")
    parser.add_argument("--backup-json", default=None)
    parser.add_argument("--clean-json", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--batch-size", type=int, default=1000)
    args = parser.parse_args()
    
    run(
        args.path,
        backup_json=args.backup_json,
        clean_json=args.clean_json,
        dry_run=args.dry_run,
        batch_size=args.batch_size
    )
