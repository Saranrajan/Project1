#!/usr/bin/env python3
import pathlib
import re
import sys

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine")
if not wine_dir.is_dir():
    print(f"Error: {wine_dir} not found", file=sys.stderr)
    sys.exit(1)

patched_count = 0

old_str = '"/tmp/.wine-%u'
new_str = '"%s/.wine-%u", (getenv("TMPDIR") && getenv("TMPDIR")[0]) ? getenv("TMPDIR") : "/tmp"'

for file_path in wine_dir.rglob("*.[ch]"):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        continue

    if "/tmp/.wine-" in content:
        print(f"Found /tmp in: {file_path}")
        new_content = content.replace(old_str, new_str)
        if new_content != content:
            file_path.write_text(new_content, encoding="utf-8")
            patched_count += 1
            print(f"Patched: {file_path}")

print(f"Total Wine source files patched for TMPDIR: {patched_count}")
