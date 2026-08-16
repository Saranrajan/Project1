#!/usr/bin/env python3
"""Patch Wine's dlls/ntdll/unix/virtual.c with an Android-compatible mprotect wrapper.

On Android, /data is mounted with SELinux policies that prevent file-backed mprotect(PROT_EXEC).
When Wine loads a PE image (ntdll.dll, kernel32.dll, apps), setting PROT_EXEC fails.

We define android_mprotect() which falls back to remapping the section as MAP_ANONYMOUS
and copying the contents, which Android allows PROT_EXEC on.
"""
import pathlib
import re
import sys

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine")
if not wine_dir.is_dir():
    print(f"Error: {wine_dir} is not a directory", file=sys.stderr)
    sys.exit(1)

patched_count = 0

helper_code = '''
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

    if "noexec filesystem" in content or "map_image_into_view" in content:
        print(f"Found virtual.c target: {file_path}")

        if "android_mprotect" in content:
            print(f"Already patched: {file_path}")
            patched_count += 1
            continue

        # Add helper function at the top after includes
        # Find last #include
        includes = list(re.finditer(r'#include\s+[<"][^>"]+[>"]', content))
        if includes:
            last_inc = includes[-1]
            insert_pos = last_inc.end()
            new_content = content[:insert_pos] + "\n" + helper_code + "\n" + content[insert_pos:]
        else:
            new_content = helper_code + "\n" + content

        # Replace mprotect calls with android_mprotect
        new_content = new_content.replace("mprotect(", "android_mprotect(")
        # In our helper itself, we need the real mprotect!
        # Fix the recursive call in helper_code
        new_content = new_content.replace(
            "if (android_mprotect( ptr, size, unix_prot ) == 0) return 0;",
            "if (mprotect( ptr, size, unix_prot ) == 0) return 0;"
        ).replace(
            "if (android_mprotect( anon_ptr, size, unix_prot ) == 0)",
            "if (mprotect( anon_ptr, size, unix_prot ) == 0)"
        )

        file_path.write_text(new_content, encoding="utf-8")
        patched_count += 1
        print(f"Successfully patched {file_path} with android_mprotect wrapper")

print(f"Total files patched: {patched_count}")
if patched_count == 0:
    print("WARNING: No virtual.c found with target strings. Searching all .c files...")
    for file_path in wine_dir.rglob("*.c"):
        try:
            content = file_path.read_text(encoding="utf-8")
        except Exception:
            continue
        if "noexec filesystem" in content:
            print(f"Found candidate: {file_path}")
            # Patch candidate
            includes = list(re.finditer(r'#include\s+[<"][^>"]+[>"]', content))
            insert_pos = includes[-1].end() if includes else 0
            new_content = content[:insert_pos] + "\n" + helper_code + "\n" + content[insert_pos:]
            new_content = new_content.replace("mprotect(", "android_mprotect(")
            new_content = new_content.replace(
                "if (android_mprotect( ptr, size, unix_prot ) == 0) return 0;",
                "if (mprotect( ptr, size, unix_prot ) == 0) return 0;"
            ).replace(
                "if (android_mprotect( anon_ptr, size, unix_prot ) == 0)",
                "if (mprotect( anon_ptr, size, unix_prot ) == 0)"
            )
            file_path.write_text(new_content, encoding="utf-8")
            patched_count += 1
            print(f"Successfully patched {file_path}")

if patched_count == 0:
    print("Error: Could not locate any Wine source file with noexec filesystem", file=sys.stderr)
    sys.exit(1)
