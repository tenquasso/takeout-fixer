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
