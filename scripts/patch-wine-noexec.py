#!/usr/bin/env python3
"""Patch Wine's dlls/ntdll/unix/virtual.c to handle Android noexec filesystem on PE sections.

On Android, application storage (/data/data/com.winlator) blocks mprotect(PROT_EXEC)
on file-backed mmap regions due to SELinux W^X policies.

When Wine loads a PE image (ntdll.dll, kernel32.dll, apps), setting PROT_EXEC fails.

This patch intercepts the mprotect failure in map_image_into_view, allocates a temporary
anonymous page with mmap(NULL, size, ...), copies the PE section data, remaps the section
at ptr with MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, restores the data, and calls mprotect(PROT_EXEC).
"""
import pathlib
import re
import sys

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine")
if not wine_dir.is_dir():
    print(f"Error: {wine_dir} is not a directory", file=sys.stderr)
    sys.exit(1)

patched_count = 0

for file_path in wine_dir.rglob("*.[ch]"):
    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception:
        continue

    if "noexec filesystem" not in content:
        continue

    print(f"Found 'noexec filesystem' in: {file_path}")

    if "noexec_ok" in content:
        print(f"Already patched: {file_path}")
        patched_count += 1
        continue

    # Use regex to find the if (mprotect(...)) block around "noexec filesystem"
    # Matches: if (mprotect( <ptr>, <size>, <prot> ) == -1) { ... ERR( ... "noexec filesystem ... ); ... return ...; }
    pattern = re.compile(
        r'(if\s*\(\s*mprotect\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)\s*==\s*-1\s*\)\s*\{)([^}]*noexec filesystem[^}]*return[^}]*;?\s*\})',
        re.DOTALL
    )

    match = pattern.search(content)
    if match:
        header = match.group(1)
        ptr_v = match.group(2)
        size_v = match.group(3)
        prot_v = match.group(4)
        body = match.group(5)

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

        replacement = header + fallback + body + "\n    noexec_ok: ;"
        new_content = content[:match.start()] + replacement + content[match.end():]
        file_path.write_text(new_content, encoding="utf-8")
        patched_count += 1
        print(f"Successfully patched {file_path} via regex match (ptr={ptr_v}, size={size_v}, prot={prot_v})")
    else:
        # Fallback string search if pattern is slightly different
        print(f"Regex didn't match directly in {file_path}, trying block-level search...")
        pos = content.find("noexec filesystem")
        # Search backwards for mprotect
        mprot_match = list(re.finditer(r'if\s*\(\s*mprotect\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)\s*==\s*-1\s*\)\s*\{', content[:pos]))
        if mprot_match:
            last_m = mprot_match[-1]
            ptr_v = last_m.group(1)
            size_v = last_m.group(2)
            prot_v = last_m.group(3)
            brace_pos = last_m.end() - 1

            ret_pos = content.find("return ", pos)
            if ret_pos != -1:
                close_b = content.find("}", ret_pos)
                if close_b != -1:
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
                    new_content = content[:brace_pos + 1] + fallback + content[brace_pos + 1:close_b + 1] + "\n    noexec_ok: ;" + content[close_b + 1:]
                    file_path.write_text(new_content, encoding="utf-8")
                    patched_count += 1
                    print(f"Successfully patched {file_path} via block search (ptr={ptr_v}, size={size_v}, prot={prot_v})")

print(f"Total files patched: {patched_count}")
if patched_count == 0:
    print("Error: Could not locate and patch 'noexec filesystem' in Wine source", file=sys.stderr)
    sys.exit(1)
