#!/usr/bin/env python3
"""Patch Wine's dlls/ntdll/unix/virtual.c with an Android-compatible mprotect wrapper.

On Android, /data is mounted with SELinux policies that prevent file-backed mprotect(PROT_EXEC).
When Wine loads a PE image (ntdll.dll, kernel32.dll, apps), setting PROT_EXEC fails.

We inject android_mprotect_compat() and a macro redirection after the last #include in virtual.c.
"""
import pathlib
import re
import sys

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine")
if not wine_dir.is_dir():
    print(f"Error: {wine_dir} is not a directory", file=sys.stderr)
    sys.exit(1)

patched_count = 0

wrapper_block = '''
/* --- BEGIN ANDROID NOEXEC / W^X COMPATIBILITY WRAPPER --- */
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

static inline int android_mprotect_compat( void *ptr, size_t size, int unix_prot )
{
    if ((mprotect)( ptr, size, unix_prot ) == 0) return 0;
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
                if ((mprotect)( anon_ptr, size, unix_prot ) == 0)
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

#undef mprotect
#define mprotect(a, b, c) android_mprotect_compat((a), (b), (c))
/* --- END ANDROID NOEXEC / W^X COMPATIBILITY WRAPPER --- */
'''

for file_path in wine_dir.rglob("virtual.c"):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        continue

    if "android_mprotect_compat" in content:
        print(f"Already patched: {file_path}")
        patched_count += 1
        continue

    print(f"Found target virtual.c: {file_path}")

    # Find the last #include in the file
    matches = list(re.finditer(r'#include\s+[<"][^>"]+[>"]', content))
    if not matches:
        print(f"Error: No #include found in {file_path}", file=sys.stderr)
        continue

    last_include = matches[-1]
    insert_pos = last_include.end()

    new_content = content[:insert_pos] + "\n" + wrapper_block + "\n" + content[insert_pos:]
    file_path.write_text(new_content, encoding="utf-8")
    patched_count += 1
    print(f"Successfully injected android_mprotect_compat into {file_path}")

print(f"Total files patched: {patched_count}")
if patched_count == 0:
    print("Error: Could not locate any virtual.c in Wine source", file=sys.stderr)
    sys.exit(1)
