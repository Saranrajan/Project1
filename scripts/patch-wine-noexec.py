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

for file_path in wine_dir.rglob("virtual.c"):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        continue

    if "noexec filesystem" in content:
        print(f"Found virtual.c target: {file_path}")

        if "android_mprotect" in content:
            print(f"Already patched: {file_path}")
            patched_count += 1
            continue

        # Find position of "noexec filesystem"
        pos = content.find("noexec filesystem")
        mprot_pos = content.rfind("mprotect(", 0, pos)
        if mprot_pos == -1:
            print(f"Error: Could not find mprotect before 'noexec filesystem' in {file_path}", file=sys.stderr)
            continue

        # Replace ONLY that specific mprotect call
        new_content = content[:mprot_pos] + "android_mprotect(" + content[mprot_pos + len("mprotect("):]

        # Insert helper_code at top of file
        new_content = helper_code + "\n" + new_content

        file_path.write_text(new_content, encoding="utf-8")
        patched_count += 1
        print(f"Successfully targeted and patched map_image_into_view in {file_path}")

print(f"Total files patched: {patched_count}")
if patched_count == 0:
    print("Error: Could not locate any Wine source file with 'noexec filesystem'", file=sys.stderr)
    sys.exit(1)
