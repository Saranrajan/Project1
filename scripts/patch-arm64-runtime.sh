#!/usr/bin/env bash
set -euo pipefail

ROOTFS="${1:?usage: patch-arm64-runtime.sh <rootfs> }"
INTERPRETER="/data/data/com.winlator/files/rootfs/lib/ld-linux-aarch64.so.1"
RPATH='$ORIGIN/../lib:$ORIGIN/../../lib/aarch64-linux-gnu:$ORIGIN/../../../lib'

command -v patchelf >/dev/null
command -v file >/dev/null

BIN_DIR="$ROOTFS/usr/local/bin"
test -d "$BIN_DIR"

patched=0
seen=""

patch_one() {
    local path="$1" target kind old_interp interp
    [ -e "$path" ] || return 0
    target="$(readlink -f "$path")"
    [ -f "$target" ] || return 0

    case "\n$seen\n" in
        *"\n$target\n"*) return 0 ;;
    esac
    seen="${seen}${target}\n"

    kind="$(file -b "$target" || true)"
    case "$kind" in
        *"ELF 64-bit LSB"*"ARM aarch64"*)
            old_interp="$(patchelf --print-interpreter "$target" 2>/dev/null || true)"
            if [ -n "$old_interp" ]; then
                echo "Patching ARM64 ELF executable: $target"
                echo "  before: $old_interp"
                patchelf --set-interpreter "$INTERPRETER" --set-rpath "$RPATH" "$target"
                interp="$(patchelf --print-interpreter "$target")"
                test "$interp" = "$INTERPRETER"
                echo "  after:  $interp"
                echo "  rpath:  $(patchelf --print-rpath "$target")"
            else
                echo "Patching ARM64 ELF library: $target"
                patchelf --set-rpath "$RPATH" "$target" 2>/dev/null || true
            fi
            patched=$((patched + 1))
            ;;
        *)
            ;;
    esac
}

# Explicitly cover Wine launch binaries across bin and lib/wine directories
for name in wine wine64 wineserver wine-preloader wine64-preloader wine-arm64; do
    patch_one "$BIN_DIR/$name"
    patch_one "$ROOTFS/usr/local/lib/wine/aarch64-unix/$name"
done

# Recursively patch all ELF files in usr/local
while IFS= read -r -d '' path; do
    patch_one "$path"
done < <(find "$ROOTFS/usr/local" -type f -print0)

if [ "$patched" -eq 0 ]; then
    echo "ERROR: no ARM64 ELF Wine/helper binaries were patched" >&2
    exit 1
fi

echo "Patched $patched unique ARM64 ELF binaries."
