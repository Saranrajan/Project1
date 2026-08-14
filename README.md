# Winlator ARM64 Native Experiment

This repository is the development workspace for an experimental Winlator-compatible Android runtime that adds native ARM64 Windows application execution while preserving x86/x64 compatibility.

## Upstream references

- Winlator: https://github.com/brunodev85/winlator
- Winlator app source: https://github.com/brunodev85/winlator-app
- Hangover: https://github.com/AndreRH/hangover

## Initial architecture decision

The existing Winlator app launches the guest executable through `box64` in `GuestProgramLauncherComponent`.

The planned execution dispatcher is:

- ARM64 Windows PE -> native ARM64 Wine/Hangover path
- x86-64 Windows PE -> existing Box64/FEX-compatible path
- x86 Windows PE -> existing WOW64/Box64-compatible path

Do not route native ARM64 applications through Box64.

## Status

Phase 1 reconnaissance complete. The next implementation phase is an ARM64-native Wine/Hangover proof of concept, isolated behind an experimental execution mode.
