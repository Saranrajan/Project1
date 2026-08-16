#!/usr/bin/env python3
"""Patch Wine's dlls/ntdll/unix/virtual.c to handle Android noexec filesystem on PE sections.

On Android, application storage (/data/data/com.winlator) blocks mprotect(PROT_EXEC)
on file-backed mmap regions due to SELinux W^X policies.

When Wine loads a PE image (ntdll.dll, kernel32.dll, apps), setting PROT_EXEC fails.

This patch intercepts the mprotect failure in map_image_into_view, allocates a temporary
anonymous page with mmap(NULL, size, ...), copies the PE section data, remaps the section
at ptr with MAP_FIXED | MAP_ANONYMOUS, restores the data, and calls mprotect(PROT_EXEC).
"""
import pathlib
import sys

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine")
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

for file_path in wine_dir.rglob("virtual.c"):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        continue

    if "noexec filesystem" in content:
        print(f"Found virtual.c target: {file_path}")

        if "noexec_ok" in content:
            print(f"Already patched: {file_path}")
            patched_count += 1
            continue

        # Find the error string
        pos = content.find("noexec filesystem")
        # Find the preceding if (mprotect(
        mprot_pos = content.rfind("if (mprotect(", 0, pos)
        if mprot_pos == -1:
            print(f"Could not find if (mprotect( before 'noexec filesystem' in {file_path}")
            continue

        # Find the opening brace after if (mprotect(...)
        brace_pos = content.find("{", mprot_pos)
        if brace_pos == -1 or brace_pos > pos:
            print(f"Could not find opening brace for mprotect error block in {file_path}")
            continue

        # Find the closing brace of the error block (after return STATUS_INVALID_IMAGE_FORMAT;)
        ret_pos = content.find("STATUS_INVALID_IMAGE_FORMAT;", pos)
        if ret_pos == -1:
            print(f"Could not find STATUS_INVALID_IMAGE_FORMAT in {file_path}")
            continue

        close_brace_pos = content.find("}", ret_pos)
        if close_brace_pos == -1:
            print(f"Could not find closing brace for error block in {file_path}")
            continue

        # Insert fallback right after the opening brace and label after closing brace
        new_content = (
            content[:brace_pos + 1]
            + noexec_fallback
            + content[brace_pos + 1:close_brace_pos + 1]
            + "\n    noexec_ok: ;"
            + content[close_brace_pos + 1:]
        )

        file_path.write_text(new_content, encoding="utf-8")
        patched_count += 1
        print(f"Successfully patched {file_path} with direct mmap anonymous fallback")

print(f"Total files patched: {patched_count}")
if patched_count == 0:
    print("Error: Could not patch virtual.c", file=sys.stderr)
    sys.exit(1)
