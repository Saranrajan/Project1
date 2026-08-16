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
    local path="$1" target kind interp
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
            echo "Patching ARM64 ELF: $target"
            echo "  before: $(patchelf --print-interpreter "$target" 2>/dev/null || echo '<none>')"
            patchelf --set-interpreter "$INTERPRETER" --set-rpath "$RPATH" "$target"
            interp="$(patchelf --print-interpreter "$target")"
            test "$interp" = "$INTERPRETER"
            echo "  after:  $interp"
            echo "  rpath:  $(patchelf --print-rpath "$target")"
            patched=$((patched + 1))
            ;;
        *)
            ;;
    esac
}

# Explicitly cover Wine launch binaries, then all ELF helper binaries.
for name in wine wine64 wineserver wine-preloader wine64-preloader wine-arm64; do
    patch_one "$BIN_DIR/$name"
done

while IFS= read -r -d '' path; do
    patch_one "$path"
done < <(find "$BIN_DIR" -maxdepth 1 -type f -print0)

if [ "$patched" -eq 0 ]; then
    echo "ERROR: no ARM64 ELF Wine/helper binaries were patched" >&2
    exit 1
fi

echo "Patched $patched unique ARM64 ELF binaries."
