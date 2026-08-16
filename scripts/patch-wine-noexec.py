#!/usr/bin/env python3
"""Patch Wine's PE loader in dlls/ntdll/unix/virtual.c to handle Android noexec filesystems.

On Android, application storage (/data/data/com.winlator) blocks mprotect(PROT_EXEC)
on file-backed mmap regions due to SELinux W^X policies.

When Wine loads a PE image (ntdll.dll, kernel32.dll, or an ARM64/ARM64EC exe),
setting PROT_EXEC on file-backed .text sections fails with EACCES/EPERM ("noexec filesystem?").

This script patches virtual.c to intercept mprotect failures on executable sections,
save the section data to a temporary buffer, remap the range with MAP_ANONYMOUS,
restore the data, and successfully apply PROT_EXEC.
"""
import pathlib
import sys
import re

wine_dir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "third_party/hangover/wine")
virtual_c = wine_dir / "dlls" / "ntdll" / "unix" / "virtual.c"

if not virtual_c.is_file():
    for alt in [wine_dir / "dlls/ntdll/virtual.c"]:
        if alt.is_file():
            virtual_c = alt
            break
    else:
        print(f"Error: {virtual_c} not found", file=sys.stderr)
        sys.exit(1)

print(f"Patching: {virtual_c}")
content = virtual_c.read_text(encoding="utf-8")
original = content

# Search for the mprotect check in map_image_into_view
# Typical pattern in Wine ntdll virtual.c:
#
# if (mprotect( ptr, size, unix_prot ) == -1)
# {
#     ERR( "failed to set %08x protection on %s section %s, noexec filesystem?\n", ... );
#     return STATUS_INVALID_IMAGE_FORMAT;
# }

replacement_code = """if (mprotect( ptr, size, unix_prot ) == -1)
    {
        /* Android noexec fallback: convert file-backed mapping to anonymous memory */
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
                        goto noexec_ok;
                }
                else
                {
                    free( tmp_buf );
                }
            }
        }
        ERR( "failed to set %08x protection on %s section %s, noexec filesystem?\\n","""

# Try targeted string replace first
old_target = """if (mprotect( ptr, size, unix_prot ) == -1)
    {
        ERR( "failed to set %08x protection on %s section %s, noexec filesystem?\\n","""

if old_target in content:
    content = content.replace(old_target, replacement_code, 1)
    # Also add the noexec_ok label right after the if-block closes
    # Find the closing brace of the error block
    idx = content.find(replacement_code)
    if idx != -1:
        end_idx = content.find("return STATUS_INVALID_IMAGE_FORMAT;\n    }", idx)
        if end_idx != -1:
            closing = "return STATUS_INVALID_IMAGE_FORMAT;\n    }"
            content = content[:end_idx] + closing + "\n    noexec_ok: ;" + content[end_idx + len(closing):]
            print("Successfully applied noexec fallback via exact string match")
else:
    # Regex fallback
    pattern = r'if\s*\(\s*mprotect\s*\(\s*(\w+)\s*,\s*(\w+)\s*,\s*(\w+)\s*\)\s*==\s*-1\s*\)\s*\{\s*ERR\s*\(\s*"failed to set [^"]*noexec filesystem[^"]*"\s*,'
    match = re.search(pattern, content)
    if match:
        p_var, s_var, u_var = match.group(1), match.group(2), match.group(3)
        dynamic_repl = f"""if (mprotect( {p_var}, {s_var}, {u_var} ) == -1)
    {{
        /* Android noexec fallback: convert file-backed mapping to anonymous memory */
        if ((errno == EACCES || errno == EPERM) && ({u_var} & PROT_EXEC))
        {{
            void *tmp_buf = malloc( {s_var} );
            if (tmp_buf)
            {{
                memcpy( tmp_buf, {p_var}, {s_var} );
                void *anon_ptr = mmap( {p_var}, {s_var}, PROT_READ | PROT_WRITE,
                                       MAP_FIXED | MAP_PRIVATE | MAP_ANONYMOUS, -1, 0 );
                if (anon_ptr != MAP_FAILED)
                {{
                    memcpy( anon_ptr, tmp_buf, {s_var} );
                    free( tmp_buf );
                    if (mprotect( anon_ptr, {s_var}, {u_var} ) == 0)
                        goto noexec_ok;
                }}
                else
                {{
                    free( tmp_buf );
                }}
            }}
        }}
        ERR( "failed to set %08x protection on %s section %s, noexec filesystem?\\n","""
        content = content[:match.start()] + dynamic_repl + content[match.end():]
        # Insert label after closing brace
        idx = content.find(dynamic_repl)
        end_idx = content.find("STATUS_INVALID_IMAGE_FORMAT;\n    }", idx)
        if end_idx != -1:
            closing = "STATUS_INVALID_IMAGE_FORMAT;\n    }"
            content = content[:end_idx] + closing + "\n    noexec_ok: ;" + content[end_idx + len(closing):]
            print("Successfully applied noexec fallback via regex match")
        else:
            print("WARNING: Could not find error return block for label insertion")
    else:
        print("ERROR: Could not find mprotect with noexec filesystem in virtual.c", file=sys.stderr)
        sys.exit(1)

if content != original:
    virtual_c.write_text(content, encoding="utf-8")
    print(f"Saved patched {virtual_c}")
else:
    print("No changes made to virtual.c", file=sys.stderr)
    sys.exit(1)
