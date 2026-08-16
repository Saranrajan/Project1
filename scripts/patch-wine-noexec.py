#!/usr/bin/env python3
"""Patch Wine's dlls/ntdll/unix/virtual.c to handle Android noexec filesystem on PE sections."""
import pathlib
import sys

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine").resolve()
print(f"[patch-wine-noexec] Search directory: {wine_dir}")

if not wine_dir.is_dir():
    print(f"Error: {wine_dir} is not a directory", file=sys.stderr)
    sys.exit(1)

patched_count = 0

# Target ONLY unix virtual.c files (never Windows/PE files)
for file_path in wine_dir.rglob("unix/virtual.c"):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        continue

    print(f"[patch-wine-noexec] Found target unix virtual.c: {file_path}")

    if "noexec_ok" in content:
        print(f"[patch-wine-noexec] Already patched: {file_path}")
        patched_count += 1
        continue

    if "noexec" in content.lower():
        idx = content.lower().find("noexec")
        # Find the opening brace of the if block before 'noexec'
        brace_pos = content.rfind("{", 0, idx)
        # Find the error return / end of this if block
        ret_pos = content.find("STATUS_INVALID_IMAGE_FORMAT", idx)
        if ret_pos != -1:
            close_b = content.find("}", ret_pos)
            if brace_pos != -1 and close_b != -1:
                # Direct in-place fallback with explicit (void*) casts
                fallback = """
        if ((errno == EACCES || errno == EPERM) && (unix_prot & PROT_EXEC))
        {
            void *tmp_buf = mmap( NULL, size, PROT_READ | PROT_WRITE, MAP_PRIVATE | MAP_ANONYMOUS, -1, 0 );
            if (tmp_buf != MAP_FAILED)
            {
                memcpy( tmp_buf, (void *)ptr, size );
                void *anon_ptr = mmap( (void *)ptr, size, PROT_READ | PROT_WRITE,
                                       MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0 );
                if (anon_ptr != MAP_FAILED)
                {
                    memcpy( anon_ptr, tmp_buf, size );
                    munmap( tmp_buf, size );
                    if (mprotect( (void *)anon_ptr, size, unix_prot ) == 0)
                        goto noexec_ok;
                }
                else
                {
                    munmap( tmp_buf, size );
                }
            }
        }"""
                new_content = (
                    content[:brace_pos + 1]
                    + fallback
                    + content[brace_pos + 1:close_b + 1]
                    + "\n    noexec_ok: ;"
                    + content[close_b + 1:]
                )
                file_path.write_text(new_content, encoding="utf-8")
                patched_count += 1
                print(f"[patch-wine-noexec] Successfully patched {file_path} with direct in-place anonymous fallback")

print(f"[patch-wine-noexec] Total files patched: {patched_count}")
