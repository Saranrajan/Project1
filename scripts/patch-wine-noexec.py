#!/usr/bin/env python3
"""Patch Wine's dlls/ntdll/unix/virtual.c with an Android-compatible mprotect wrapper for PE loading.

On Android, /data is mounted with SELinux policies that prevent file-backed mprotect(PROT_EXEC).
When Wine loads a PE image (ntdll.dll, kernel32.dll, apps), setting PROT_EXEC fails.

We define android_mprotect() which falls back to remapping the section as MAP_ANONYMOUS
and copying the contents, which Android allows PROT_EXEC on.
"""
import pathlib
import sys

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine")
if not wine_dir.is_dir():
    print(f"Error: {wine_dir} is not a directory", file=sys.stderr)
    sys.exit(1)

patched_count = 0

helper_code = '''
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#ifndef MAP_ANONYMOUS
#ifdef MAP_ANON
#define MAP_ANONYMOUS MAP_ANON
#else
#define MAP_ANONYMOUS 0x20
#endif
#endif

/* Android W^X / noexec filesystem compatibility wrapper */
static inline int android_mprotect( void *ptr, size_t size, int unix_prot )
{
    if (mprotect( ptr, size, unix_prot ) == 0) return 0;
    if ((errno == EACCES || errno == EPERM) && (unix_prot & PROT_EXEC))
    {
        void *tmp_buf = malloc( size );
        if (tmp_buf)
        {
            memcpy( tmp_buf, ptr, size );
            void *anon_ptr = mmap( ptr, size, PROT_READ | PROT_WRITE,
                                   MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0 );
            if (anon_ptr != MAP_FAILED)
            {
                memcpy( anon_ptr, tmp_buf, size );
                free( tmp_buf );
                if (mprotect( anon_ptr, size, unix_prot ) == 0)
                    return 0;
            }
            else
            {
                free( tmp_buf );
            }
        }
    }
    return -1;
}
'''

for file_path in wine_dir.rglob("*.c"):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        continue

    if "map_image_into_view" in content:
        print(f"Found map_image_into_view in: {file_path}")

        if "android_mprotect" in content:
            print(f"Already patched: {file_path}")
            patched_count += 1
            continue

        # Find start of map_image_into_view
        func_pos = content.find("map_image_into_view")
        # Find opening brace of the function
        brace_pos = content.find("{", func_pos)
        if brace_pos == -1:
            print(f"Could not find opening brace for map_image_into_view in {file_path}")
            continue

        # Find the end of map_image_into_view by tracking brace depth
        depth = 0
        end_pos = -1
        for i in range(brace_pos, len(content)):
            if content[i] == '{':
                depth += 1
            elif content[i] == '}':
                depth -= 1
                if depth == 0:
                    end_pos = i + 1
                    break

        if end_pos == -1:
            print(f"Could not find closing brace for map_image_into_view in {file_path}")
            continue

        func_body = content[brace_pos:end_pos]
        # Replace mprotect inside map_image_into_view ONLY
        patched_func_body = func_body.replace("mprotect(", "android_mprotect(")

        new_content = helper_code + "\n" + content[:brace_pos] + patched_func_body + content[end_pos:]

        file_path.write_text(new_content, encoding="utf-8")
        patched_count += 1
        print(f"Successfully patched map_image_into_view in {file_path}")

print(f"Total files patched: {patched_count}")
if patched_count == 0:
    print("Error: Could not locate map_image_into_view in any Wine source file", file=sys.stderr)
    sys.exit(1)
