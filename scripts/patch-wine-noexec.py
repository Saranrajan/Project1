#!/usr/bin/env python3
"""Patch Wine's virtual.c to handle Android noexec filesystem on PE sections."""
import pathlib
import re
import sys

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine").resolve()
print(f"[patch-wine-noexec] Search directory: {wine_dir}")

if not wine_dir.is_dir():
    print(f"Error: {wine_dir} is not a directory", file=sys.stderr)
    sys.exit(1)

helper_fn = '''
#include <errno.h>
#include <string.h>
#include <sys/mman.h>

#ifndef MAP_ANONYMOUS
#ifdef MAP_ANON
#define MAP_ANONYMOUS MAP_ANON
#else
#define MAP_ANONYMOUS 0x20
#endif
#endif

static int android_mprotect( void *ptr, size_t size, int unix_prot )
{
    if (mprotect( ptr, size, unix_prot ) == 0) return 0;
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
                    return 0;
            }
            else
            {
                munmap( tmp_buf, size );
            }
        }
    }
    return -1;
}
'''

patched_count = 0

for file_path in wine_dir.rglob("*.[ch]"):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        continue

    if "noexec" in content.lower() and "mprotect" in content:
        print(f"[patch-wine-noexec] Found candidate: {file_path}")

        if "android_mprotect" in content:
            print(f"[patch-wine-noexec] Already patched: {file_path}")
            patched_count += 1
            continue

        # Find position of 'noexec'
        idx = content.lower().find("noexec")
        # Find the mprotect call right before idx
        m_idx = content.rfind("mprotect", 0, idx)
        if m_idx != -1:
            # Replace mprotect with android_mprotect
            new_content = content[:m_idx] + "android_mprotect" + content[m_idx + len("mprotect"):]

            # Find the last #include in the file to insert helper_fn safely
            includes = list(re.finditer(r'#include\s+[<"][^>"]+[>"]', new_content))
            if includes:
                insert_pos = includes[-1].end()
                new_content = new_content[:insert_pos] + "\n" + helper_fn + "\n" + new_content[insert_pos:]
            else:
                new_content = helper_fn + "\n" + new_content

            file_path.write_text(new_content, encoding="utf-8")
            patched_count += 1
            print(f"[patch-wine-noexec] Successfully patched {file_path} (mprotect replaced & helper inserted after includes)")

print(f"[patch-wine-noexec] Total files patched: {patched_count}")
