#!/usr/bin/env python3
import pathlib
import re
import sys

def patch_winnt(wine_dir: pathlib.Path):
    winnt_path = wine_dir / "include" / "winnt.h"
    if not winnt_path.exists():
        print(f"Warning: {winnt_path} not found")
        return False
    
    text = winnt_path.read_text(encoding="utf-8", errors="replace")
    original = text
    
    # 1. InterlockedExchange atomic builtin for clang
    pattern_interlocked = r'#if\s+\(__GNUC__\s*>\s*4\)\s*\|\|\s*\(\(__GNUC__\s*==\s*4\)\s*&&\s*\(__GNUC_MINOR__\s*>=\s*7\)\)'
    replacement_interlocked = '#if (__GNUC__ > 4) || ((__GNUC__ == 4) && (__GNUC_MINOR__ >= 7)) || defined(__clang__)'
    text = re.sub(pattern_interlocked, replacement_interlocked, text)
    
    # 2. __fastfail inline assembly for arm64ec
    # Upstream winnt.h __fastfail:
    # #if defined(__x86_64__) || defined(__i386__)
    #     for (;;) __asm__ __volatile__( "int $0x29" :: "c" ((ULONG_PTR)code) : "memory" );
    # #elif defined(__aarch64__)
    #     register ULONG_PTR val __asm__("x0") = code;
    #     for (;;) __asm__ __volatile__( "brk #0xf003" :: "r" (val) : "memory" );
    pattern_fastfail = (
        r'(static\s+FORCEINLINE\s+DECLSPEC_NORETURN\s+void\s+__fastfail\s*\([^)]*\)\s*\{[\s\r\n]*)'
        r'#if\s+defined\(__x86_64__\)\s*\|\|\s*defined\(__i386__\)[\s\r\n]+'
        r'for\s*\(\s*;\s*;\s*\)\s*__asm__\s*__volatile__\s*\(\s*"int\s+\$0x29"[^;]+;\s*[\r\n]+'
        r'#elif\s+defined\(__aarch64__\)[\s\r\n]+'
        r'register\s+ULONG_PTR\s+val\s+__asm__\("x0"\)\s*=\s*code;\s*[\r\n]+'
        r'for\s*\(\s*;\s*;\s*\)\s*__asm__\s*__volatile__\s*\(\s*"brk\s+#0xf003"[^;]+;\s*'
    )
    replacement_fastfail = (
        r'\1'
        r'#if defined(__aarch64__) || defined(__arm64ec__)\n'
        r'    register ULONG_PTR val __asm__("x0") = code;\n'
        r'    for (;;) __asm__ __volatile__( "brk #0xf003" :: "r" (val) : "memory" );\n'
        r'#elif defined(__x86_64__) || defined(__i386__)\n'
        r'    for (;;) __asm__ __volatile__( "int $0x29" :: "c" ((ULONG_PTR)code) : "memory" );\n'
    )
    text = re.sub(pattern_fastfail, replacement_fastfail, text)
    
    # Generic fastfail fallback if specific pattern didn't match
    if "__arm64ec__" not in text and "__fastfail" in text:
        text = text.replace(
            '#if defined(__x86_64__) || defined(__i386__)\n    for (;;) __asm__ __volatile__( "int $0x29"',
            '#if defined(__aarch64__) || defined(__arm64ec__)\n    register ULONG_PTR val __asm__("x0") = code;\n    for (;;) __asm__ __volatile__( "brk #0xf003" :: "r" (val) : "memory" );\n#elif defined(__x86_64__) || defined(__i386__)\n    for (;;) __asm__ __volatile__( "int $0x29"'
        )
    
    if text != original:
        winnt_path.write_text(text, encoding="utf-8", newline="\n")
        print(f"Successfully patched {winnt_path}")
        return True
    else:
        print(f"No changes needed or could not pattern match in {winnt_path}")
        return False

def patch_tomcrypt(wine_dir: pathlib.Path):
    patched_any = False
    for tc_path in wine_dir.glob("**/tomcrypt_macros.h"):
        text = tc_path.read_text(encoding="utf-8", errors="replace")
        original = text
        
        # Disallow x86 inline asm in LibTomCrypt for ARM64EC
        pattern = r'(#if\s+!defined\(__STRICT_ANSI__\)\s*&&\s*defined\(__GNUC__\)\s*&&\s*\(defined\(__i386__\)\s*\|\|\s*defined\(__x86_64__\)\))'
        if "__arm64ec__" not in text:
            text = re.sub(pattern, r'\1 && !defined(__arm64ec__)', text)
            
        if text != original:
            tc_path.write_text(text, encoding="utf-8", newline="\n")
            print(f"Successfully patched {tc_path}")
            patched_any = True
            
    return patched_any

def main():
    wine_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("third_party/hangover/wine")
    print(f"Applying Hangover Wine ARM64EC patches in {wine_dir}...")
    w_ok = patch_winnt(wine_dir)
    t_ok = patch_tomcrypt(wine_dir)
    print(f"Patching results: winnt.h: {w_ok}, tomcrypt: {t_ok}")

if __name__ == "__main__":
    main()
