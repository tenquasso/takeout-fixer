import os
import sys
import json
import subprocess
from datetime import datetime

def parse_json(json_path):
    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return int(data['photoTakenTime']['timestamp'])

def run(target_dir):
    for root, dirs, files in os.walk(target_dir):
        for f in files:
            if f.endswith('.jpg'):
                json_file = os.path.join(root, f + '.json')
                if os.path.exists(json_file):
                    ts = parse_json(json_file)
                    dt = datetime.fromtimestamp(ts).strftime('%Y:%m:%d %H:%M:%S')
                    subprocess.run(['exiftool', '-overwrite_original', f'-AllDates={dt}', os.path.join(root, f)])

if __name__ == '__main__':
    run(sys.argv[1] if len(sys.argv) > 1 else '.')
