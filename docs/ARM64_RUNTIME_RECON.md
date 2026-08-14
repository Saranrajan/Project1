# ARM64 Native Runtime Reconnaissance

## Findings

### Upstream Winlator
The current Winlator Android application uses a dedicated `GuestProgramLauncherComponent` to launch guest executables. The launcher currently constructs:

`<root>/usr/local/bin/box64 <guestExecutable>`

This means the current launcher unconditionally enters the Box64 path.

### Winlator container model
`Container.java` already stores CPU lists, a separate WoW64 CPU list, Wine version, Box64 preset, graphics driver, DX wrapper, environment variables, and persistent extra data. This gives us room to add an execution-backend setting without replacing the existing container model.

### Wine version
Current Winlator app source identifies its built-in Wine as version `10.10` (`wine-10.10-custom`).

### Current Hangover
Current upstream Hangover runs Win32/Win64 applications on AArch64 Wine. Its architecture is explicitly designed to emulate only application code while Wine/system calls remain native. ARM64 applications such as ARM64 7-Zip can run natively. Current 64-bit x86 emulation uses ARM64EC plus FEX; 32-bit paths can use FEX or Box64 WOW64 DLLs.

### Current Hangover build requirements
Current Hangover builds Wine with `--with-mingw=clang --enable-archs=arm64ec,aarch64,i386`. Its FEX ARM64EC DLL is required for x86_64 application emulation. Optional components exist for 32-bit FEX and Box64 WOW64.

### Old Android Hangover repository
`gmh5225/emu-wine-android-hangover` is an older Hangover generation using QEMU 5.2 and a Wine submodule. It is historical reference material rather than the preferred runtime base because current Hangover has moved to ARM64EC/FEX and Box64 PE integrations.

## Architecture decision

Do not port the old Android QEMU Hangover stack into Winlator.

Preferred direction:

1. Use a current ARM64/WoW64 Wine base compatible with Hangover's architecture.
2. Keep native AArch64 Windows PE execution entirely outside CPU emulation.
3. Use ARM64EC/FEX for x86_64 Windows applications.
4. Use WOW64 FEX/Box64 for x86 applications where necessary.
5. Preserve Winlator's existing Box64 launcher as the compatibility fallback.
6. Add an architecture-aware execution dispatcher at the current `GuestProgramLauncherComponent` boundary.

## Critical compatibility question

Winlator currently packages/installs a custom Wine 10.10 runtime and its root filesystem. We need to verify whether that Wine build already contains the ARM64 PE/WoW64 plumbing required by current Hangover. If not, a dedicated ARM64 Wine runtime must be built and packaged alongside the existing x86_64-oriented runtime rather than attempting to retrofit ARM64 execution into the Box64 binary.

## Next implementation milestone

Build a standalone ARM64 Wine/Hangover runtime proof-of-concept for Android/ARM64 and verify execution of a trivial ARM64 Windows PE. Only after that succeeds should the launcher dispatcher be implemented.
