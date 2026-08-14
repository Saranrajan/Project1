#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HANGOVER_DIR="${ROOT_DIR}/third_party/hangover"
LLVM_MINGW_BIN="${LLVM_MINGW_BIN:-}"

if [[ ! -d "${HANGOVER_DIR}" ]]; then
  echo "Hangover submodule is missing. Run: git submodule update --init --recursive" >&2
  exit 1
fi

if [[ -z "${LLVM_MINGW_BIN}" ]]; then
  echo "Set LLVM_MINGW_BIN to the directory containing llvm-mingw binaries." >&2
  exit 1
fi

export PATH="${LLVM_MINGW_BIN}:${PATH}"

mkdir -p "${HANGOVER_DIR}/wine/build"
cd "${HANGOVER_DIR}/wine/build"

if [[ ! -f Makefile ]]; then
  ../configure \
    --disable-tests \
    --with-mingw=clang \
    --enable-archs=arm64ec,aarch64,i386
fi

make -j"$(nproc)"

echo "Hangover ARM64 Wine build completed."
