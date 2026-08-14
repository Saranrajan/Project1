#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT_DIR}/winlator-app"
JAVA_TARGET="${APP_DIR}/app/src/main/java/com/winlator/xenvironment/components/NativeGuestDispatcher.java"
LAUNCHER="${APP_DIR}/app/src/main/java/com/winlator/xenvironment/components/GuestProgramLauncherComponent.java"
OVERLAY="${ROOT_DIR}/overlay/com/winlator/xenvironment/components/NativeGuestDispatcher.java"

[[ -d "${APP_DIR}" ]] || { echo "Missing winlator-app checkout" >&2; exit 1; }
[[ -f "${OVERLAY}" ]] || { echo "Missing overlay dispatcher" >&2; exit 1; }
[[ -f "${LAUNCHER}" ]] || { echo "Missing upstream launcher: ${LAUNCHER}" >&2; exit 1; }

mkdir -p "$(dirname "${JAVA_TARGET}")"
cp "${OVERLAY}" "${JAVA_TARGET}"

python3 - "${LAUNCHER}" <<'PY'
import pathlib
import re
import sys

path = pathlib.Path(sys.argv[1])
text = path.read_text(encoding="utf-8")
pattern = r'String command\s*=\s*rootDir\+"/usr/local/bin/box64 "\+guestExecutable;'
replacement = 'String command = NativeGuestDispatcher.buildCommand(rootDir, guestExecutable);'
text2, count = re.subn(pattern, replacement, text, count=1)
if count != 1:
    raise SystemExit("Could not locate upstream Box64 launch command; refusing to patch")
path.write_text(text2, encoding="utf-8")
PY

echo "Applied Project1 ARM64 guest dispatcher overlay."
