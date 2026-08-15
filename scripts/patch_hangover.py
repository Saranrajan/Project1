#!/usr/bin/env python3
import pathlib
import re
import sys

def patch_winnt(wine_dir: pathlib.Path) -> bool:
    winnt_path = wine_dir / "include" / "winnt.h"
    if not winnt_path.exists():
        print(f"Error: {winnt_path} not found")
        return False
    
    text = winnt_path.read_text(encoding="utf-8", errors="replace")
    original = text
    
    # 1. InterlockedExchange atomic builtins for clang
    text = re.sub(
        r'#if\s+\(__GNUC__\s*>\s*4\)\s*\|\|\s*\(\(__GNUC__\s*==\s*4\)\s*&&\s*\(__GNUC_MINOR__\s*>=\s*7\)\)',
        '#if (__GNUC__ > 4) || ((__GNUC__ == 4) && (__GNUC_MINOR__ >= 7)) || defined(__clang__)',
        text
    )
    
    # 2. Complete __fastfail replacement for ARM64EC / ARM64
    fastfail_pattern = r'static\s+FORCEINLINE\s+DECLSPEC_NORETURN\s+void\s+__fastfail\s*\([^)]*\)\s*\{[\s\S]*?\}'
    fastfail_replacement = '''static FORCEINLINE DECLSPEC_NORETURN void __fastfail(unsigned int code)
{
#if defined(__arm64ec__) || defined(__aarch64__)
    register ULONG_PTR val __asm__("x0") = code;
    for (;;) __asm__ __volatile__( "brk #0xf003" :: "r" (val) : "memory" );
#elif defined(__x86_64__) || defined(__i386__)
    for (;;) __asm__ __volatile__( "int $0x29" :: "c" ((ULONG_PTR)code) : "memory" );
#elif defined(__arm__)
    register ULONG_PTR val __asm__("r0") = code;
    for (;;) __asm__ __volatile__( "udf #0xfb" :: "r" (val) : "memory" );
#else
    for (;;) ;
#endif
}'''
    text, ff_count = re.subn(fastfail_pattern, fastfail_replacement, text, count=1)
    print(f"Patched __fastfail in winnt.h: count={ff_count}")
    if ff_count != 1:
        print("Error: Failed to match and replace __fastfail in winnt.h")
        return False
        
    if "defined(__clang__)" not in text:
        print("Error: Failed to patch InterlockedExchange for clang in winnt.h")
        return False
        
    winnt_path.write_text(text, encoding="utf-8", newline="\n")
    print(f"Successfully patched {winnt_path}")
    return True

def patch_tomcrypt(wine_dir: pathlib.Path) -> bool:
    found_any = False
    for tc_path in wine_dir.glob("**/tomcrypt_macros.h"):
        found_any = True
        text = tc_path.read_text(encoding="utf-8", errors="replace")
        original = text
        
        # Disallow x86 inline asm in LibTomCrypt for ARM64EC
        pattern = r'(#if\s+!defined\(__STRICT_ANSI__\)\s*&&\s*defined\(__GNUC__\)\s*&&\s*\(defined\(__i386__\)\s*\|\|\s*defined\(__x86_64__\)\))'
        if "__arm64ec__" not in text:
            text = re.sub(pattern, r'\1 && !defined(__arm64ec__)', text)
            
        if text != original:
            tc_path.write_text(text, encoding="utf-8", newline="\n")
            print(f"Successfully patched {tc_path}")
        else:
            print(f"tomcrypt_macros.h already patched or pattern matched: {tc_path}")
            
    if not found_any:
        print(f"Warning: No tomcrypt_macros.h found under {wine_dir}")
    return True

def main():
    wine_dir = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("third_party/hangover/wine")
    print(f"Applying Hangover Wine ARM64EC patches in {wine_dir}...")
    w_ok = patch_winnt(wine_dir)
    t_ok = patch_tomcrypt(wine_dir)
    print(f"Patching results: winnt.h: {w_ok}, tomcrypt: {t_ok}")
    if not (w_ok and t_ok):
        print("Error: Patching failed!")
        sys.exit(1)
    print("All ARM64EC patches applied successfully!")

if __name__ == "__main__":
    main()
