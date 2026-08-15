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

python3 - "${LAUNCHER}" "${ROOTFS_INSTALLER}" "${APP_DIR}" <<'PY'
import pathlib
import re
import sys

launcher = pathlib.Path(sys.argv[1])
rootfs = pathlib.Path(sys.argv[2])
app_dir = pathlib.Path(sys.argv[3])

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

# Fix upstream missing IntArray_indexOf in C/C++ runtime (required by gladiorenderer)
arrays_h = app_dir / "app/src/main/cpp/winlator/include/arrays.h"
if arrays_h.is_file():
    text = arrays_h.read_text(encoding="utf-8")
    if "IntArray_indexOf" not in text:
        inline_func = """
static inline int IntArray_indexOf(const IntArray* intArray, int value) {
    if (!intArray || !intArray->values) return -1;
    for (int i = 0; i < intArray->size; i++) {
        if (intArray->values[i] == value) return i;
    }
    return -1;
}
"""
        idx = text.rfind("#endif")
        if idx == -1:
            raise SystemExit("Could not find #endif in arrays.h")
        text = text[:idx] + inline_func + "\n" + text[idx:]
        arrays_h.write_text(text, encoding="utf-8")
        print("Patched arrays.h with static inline IntArray_indexOf")

arrays_c = app_dir / "app/src/main/cpp/winlator/src/arrays.c"
if arrays_c.is_file():
    text = arrays_c.read_text(encoding="utf-8")
    if "IntArray_indexOf" not in text:
        func = """
int IntArray_indexOf(IntArray* intArray, int value) {
    if (!intArray || !intArray->values) return -1;
    for (int i = 0; i < intArray->size; i++) {
        if (intArray->values[i] == value) return i;
    }
    return -1;
}
"""
        text = text + "\n" + func
        arrays_c.write_text(text, encoding="utf-8")
        print("Patched arrays.c with IntArray_indexOf")

arb_c = app_dir / "app/src/main/cpp/gladiorenderer/src/arb_program.c"
if arb_c.is_file():
    text = arb_c.read_text(encoding="utf-8")
    if "IntArray_indexOf" not in text or "static inline int IntArray_indexOf" not in text:
        func = """#include "gl_context.h"
#include "arrays.h"

static inline int IntArray_indexOf(const IntArray* intArray, int value) {
    if (!intArray || !intArray->values) return -1;
    for (int i = 0; i < intArray->size; i++) {
        if (intArray->values[i] == value) return i;
    }
    return -1;
}"""
        text = text.replace('#include "gl_context.h"', func, 1)
        arb_c.write_text(text, encoding="utf-8")
        print("Patched arb_program.c with local static inline IntArray_indexOf")

# Configure packagingOptions to handle duplicate JNI library symbols across CMake and prebuilts
build_gradle = app_dir / "app/build.gradle"
if build_gradle.is_file():
    text = build_gradle.read_text(encoding="utf-8")
    if "packagingOptions" not in text:
        pattern = r'(ndkVersion\s+[\'"][^\'"]+[\'"])'
        replacement = r'\1\n\n    packagingOptions {\n        jniLibs {\n            pickFirsts += [\'**/*.so\']\n        }\n    }'
        text2, count = re.subn(pattern, replacement, text, count=1)
        if count == 1:
            build_gradle.write_text(text2, encoding="utf-8")
            print("Patched app/build.gradle with packagingOptions jniLibs pickFirsts")
PY

echo "Applied Project1 ARM64 runtime and launcher overlays."
