#!/usr/bin/env python3
"""Patch Wine's dlls/ntdll/unix/virtual.c to handle Android noexec filesystem on PE sections."""
import pathlib
import re
import sys

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine").resolve()
print(f"[patch-wine-noexec] Wine search directory: {wine_dir}")

if not wine_dir.is_dir():
    print(f"Error: {wine_dir} is not a directory", file=sys.stderr)
    sys.exit(1)

patched_count = 0

noexec_fallback = """
        if ((errno == EACCES || errno == EPERM) && (unix_prot & PROT_EXEC))
        {
            void *tmp_buf = mmap( NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0 );
            if (tmp_buf != MAP_FAILED)
            {
                memcpy( tmp_buf, ptr, size );
                void *anon_ptr = mmap( ptr, size, PROT_READ | PROT_WRITE,
                                       MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0 );
                if (anon_ptr != MAP_FAILED)
                {
                    memcpy( anon_ptr, tmp_buf, size );
                    munmap( tmp_buf, size );
                    if (mprotect( anon_ptr, size, unix_prot ) == 0)
                        goto noexec_ok;
                }
                else
                {
                    munmap( tmp_buf, size );
                }
            }
        }"""

# Locate virtual.c files
candidates = list(wine_dir.rglob("virtual.c"))
print(f"[patch-wine-noexec] Found {len(candidates)} candidate virtual.c files: {[str(c) for c in candidates]}")

for file_path in candidates:
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        print(f"[patch-wine-noexec] Could not read {file_path}: {e}")
        continue

    print(f"[patch-wine-noexec] Examining: {file_path} ({len(content)} chars)")

    if "noexec_ok" in content:
        print(f"[patch-wine-noexec] Already patched: {file_path}")
        patched_count += 1
        continue

    # Look for map_image_into_view or noexec filesystem or mprotect
    if "map_image_into_view" in content or "noexec" in content.lower():
        print(f"[patch-wine-noexec] Found match in {file_path}")

        # Find mprotect calls inside map_image_into_view
        # Strategy: find map_image_into_view and find the mprotect call inside it
        pos = content.find("map_image_into_view")
        if pos == -1:
            pos = content.lower().find("noexec")

        # Search for mprotect call after pos
        mprot_match = re.search(r'if\s*\(\s*mprotect\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)\s*==\s*-1\s*\)\s*\{', content[pos:])
        if mprot_match:
            match_start = pos + mprot_match.start()
            match_end = pos + mprot_match.end()
            ptr_v = mprot_match.group(1)
            size_v = mprot_match.group(2)
            prot_v = mprot_match.group(3)
            print(f"[patch-wine-noexec] Matched mprotect at {match_start}: ptr={ptr_v}, size={size_v}, prot={prot_v}")

            # Find the closing brace of this if block
            # Look for the return statement inside this block
            ret_match = re.search(r'return\s+[^;]+;', content[match_end:])
            if ret_match:
                ret_pos = match_end + ret_match.end()
                close_brace_pos = content.find("}", ret_pos)
                if close_brace_pos != -1:
                    fallback = f"""
        if ((errno == EACCES || errno == EPERM) && ({prot_v} & PROT_EXEC))
        {{
            void *tmp_buf = mmap( NULL, {size_v}, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0 );
            if (tmp_buf != MAP_FAILED)
            {{
                memcpy( tmp_buf, {ptr_v}, {size_v} );
                void *anon_ptr = mmap( {ptr_v}, {size_v}, PROT_READ | PROT_WRITE,
                                       MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0 );
                if (anon_ptr != MAP_FAILED)
                {{
                    memcpy( anon_ptr, tmp_buf, {size_v} );
                    munmap( tmp_buf, {size_v} );
                    if (mprotect( anon_ptr, {size_v}, {prot_v} ) == 0)
                        goto noexec_ok;
                }}
                else
                {{
                    munmap( tmp_buf, {size_v} );
                }}
            }}
        }}"""
                    new_content = (
                        content[:match_end]
                        + fallback
                        + content[match_end:close_brace_pos + 1]
                        + "\n    noexec_ok: ;"
                        + content[close_brace_pos + 1:]
                    )
                    file_path.write_text(new_content, encoding="utf-8")
                    patched_count += 1
                    print(f"[patch-wine-noexec] Successfully patched {file_path} with anonymous fallback")
                else:
                    print(f"[patch-wine-noexec] Could not find closing brace after return in {file_path}")
            else:
                print(f"[patch-wine-noexec] Could not find return after mprotect in {file_path}")
        else:
            print(f"[patch-wine-noexec] Could not find mprotect pattern after pos in {file_path}")

print(f"[patch-wine-noexec] Total files patched: {patched_count}")
if patched_count == 0:
    print("[patch-wine-noexec] ERROR: No files were patched!", file=sys.stderr)
    sys.exit(1)
