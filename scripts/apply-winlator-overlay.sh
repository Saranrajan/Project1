#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP_DIR="${ROOT_DIR}/winlator-app"
JAVA_DIR="${APP_DIR}/app/src/main/java/com/winlator/xenvironment/components"
DISPATCHER_OVERLAY="${ROOT_DIR}/overlay/com/winlator/xenvironment/components/NativeGuestDispatcher.java"
DISPATCHER_TARGET="${JAVA_DIR}/NativeGuestDispatcher.java"
LAUNCHER="${JAVA_DIR}/GuestProgramLauncherComponent.java"
ROOTFS_INSTALLER="${APP_DIR}/app/src/main/java/com/winlator/xenvironment/RootFSInstaller.java"

[[ -d "${APP_DIR}" ]] || { echo "Missing winlator-app checkout" >&2; exit 1; }
[[ -f "${DISPATCHER_OVERLAY}" ]] || { echo "Missing ARM64 dispatcher overlay" >&2; exit 1; }
[[ -f "${LAUNCHER}" ]] || { echo "Missing upstream launcher: ${LAUNCHER}" >&2; exit 1; }
[[ -f "${ROOTFS_INSTALLER}" ]] || { echo "Missing upstream RootFSInstaller: ${ROOTFS_INSTALLER}" >&2; exit 1; }

mkdir -p "${JAVA_DIR}"
cp "${DISPATCHER_OVERLAY}" "${DISPATCHER_TARGET}"

python3 - "${LAUNCHER}" "${ROOTFS_INSTALLER}" <<'PY'
import pathlib
import re
import sys

launcher = pathlib.Path(sys.argv[1])
rootfs = pathlib.Path(sys.argv[2])

text = launcher.read_text(encoding="utf-8")
pattern = r'String command\s*=\s*rootDir\+"/usr/local/bin/box64 "\+guestExecutable;'
replacement = 'String command = NativeGuestDispatcher.buildCommand(rootDir, guestExecutable);'
text2, count = re.subn(pattern, replacement, text, count=1)
if count != 1:
    raise SystemExit("Could not locate upstream Box64 launch command; refusing to patch")
launcher.write_text(text2, encoding="utf-8")

text = rootfs.read_text(encoding="utf-8")
text2, count = re.subn(r'LATEST_VERSION = 21', 'LATEST_VERSION = 22', text, count=1)
if count != 1:
    raise SystemExit("Unexpected RootFSInstaller version; refusing to patch")

needle = '''            boolean success = TarCompressorUtils.extract(TarCompressorUtils.Type.ZSTD, activity, FILENAME, rootDir, (file, size) -> {
'''
if needle not in text2:
    raise SystemExit("Could not locate rootfs extraction block; refusing to patch")

marker = '''            });

            if (success) {
'''
replacement2 = '''            });

            if (success) {
                boolean nativeWineSuccess = TarCompressorUtils.extract(TarCompressorUtils.Type.ZSTD, activity, "native_arm64_wine.tzst", rootDir);
                success = nativeWineSuccess;
            }

            if (success) {
'''
text3, count = text2.replace(marker, replacement2, 1), 1
if marker not in text2:
    raise SystemExit("Could not locate rootfs success block; refusing to patch")
rootfs.write_text(text3, encoding="utf-8")
PY

echo "Applied Project1 ARM64 runtime and launcher overlays."
