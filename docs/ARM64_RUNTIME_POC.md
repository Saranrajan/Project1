# ARM64 Native Runtime POC

## Goal

Prove that an ARM64 Windows PE can execute natively on ARM64 Linux/Wine without passing its application code through Box64.

## Selected runtime

Use current upstream Hangover as the reference implementation. Current Hangover uses AArch64 Wine with WoW64, supports native ARM64 Windows applications, and uses ARM64EC/FEX for x86-64 applications. Do not reuse the old QEMU-based Android Hangover implementation as the production design.

## POC stages

1. Build Hangover Wine for AArch64 with `--enable-archs=arm64ec,aarch64,i386`.
2. Package the minimum Wine runtime and supporting libraries for an Android-compatible root filesystem.
3. Run a trivial ARM64 Windows PE with the native AArch64 Wine loader.
4. Run ARM64 7-Zip as the first practical application test.
5. Only after native execution is proven, integrate architecture dispatch into Winlator.

## Expected dispatch

```text
Windows PE
   |
   +-- ARM64   -> native ARM64 Wine/Hangover
   +-- x86_64  -> ARM64EC/FEX path
   +-- x86     -> WOW64/FEX/Box64 path
```

## Integration point

Winlator's current `GuestProgramLauncherComponent` constructs `/usr/local/bin/box64 <guestExecutable>`. The eventual change should replace this unconditional command with an architecture-aware dispatcher. The existing x86/x64 behavior must remain unchanged when the native ARM64 path is unavailable.

## Important constraint

The GitHub connector can inspect and modify source files but cannot execute a full Android NDK build on a local runner. Build validation therefore requires either GitHub Actions or a local checkout with the required toolchain. Do not claim the runtime is working until an actual ARM64 PE execution test passes.
