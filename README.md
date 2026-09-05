# google-photos-takeout-fixer

quick script to merge google takeout json metadata back into photos and videos.

when you export google photos using takeout, all metadata (date taken, gps, description) gets separated into `.json` sidecar files. if you try to re-upload them or view in standard galleries, dates get messed up to the download date. this script embeds everything back into exif/quicktime tags and updates file creation/modified timestamps.

### what it fixes
- embeds date taken into exif (`DateTimeOriginal`, `CreateDate`, `ModifyDate`)
- embeds video creation dates for mp4/mov (`QuickTime:CreateDate`, `Keys:CreationDate`)
- injects gps coordinates (latitude, longitude, altitude)
- injects descriptions/captions
- updates windows file creation & last write times
- handles takeout naming quirks (duplicate `(1)` files, truncated names, edited versions)

### requirements
- python 3.8+
- [exiftool](https://exiftool.org/) (make sure it's in your PATH or installed on your system)

on windows via winget:
```bash
winget install OliverBetz.ExifTool
```

### where to put the script & folder setup
you can use it in two ways:

1. **keep the script in your project/tools repo** and just pass the path to your extracted takeout folder:
```bash
python restore_metadata.py "D:/Takeout/Google Photos"
```

2. **or drop `restore_metadata.py` directly inside** your takeout `Google Photos` folder and run it without any path:
```bash
python restore_metadata.py
```

the script scans recursively, so all subfolders (`Photos from 2021`, `Photos from 2022`, albums, etc.) are processed automatically. just make sure the `.json` sidecars are in the same folder as their corresponding media files (which is how google takeout extracts them by default).

### usage

test first without modifying anything:
```bash
python restore_metadata.py "path/to/Google Photos" --dry-run
```

restore metadata and move json files to a backup folder:
```bash
python restore_metadata.py "path/to/Google Photos" --backup-json "path/to/json_backup"
```

restore metadata and delete json files directly:
```bash
python restore_metadata.py "path/to/Google Photos" --clean-json
```

just restore metadata in-place (keeps json alongside):
```bash
python restore_metadata.py "path/to/Google Photos"
```
