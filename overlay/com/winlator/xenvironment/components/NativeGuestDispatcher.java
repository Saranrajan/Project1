package com.winlator.xenvironment.components;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;
import java.util.Locale;

/**
 * Architecture-aware guest launcher used by the Project1 overlay.
 *
 * ARM64 Windows PE files are eligible for the native ARM64 Wine path only
 * when /usr/local/bin/wine-arm64 exists in the container. Otherwise the
 * existing Box64 command is returned unchanged.
 */
public final class NativeGuestDispatcher {
    private static final int PE_ARM64 = 0xAA64;
    private static final int PE_X86 = 0x014C;
    private static final int PE_X64 = 0x8664;

    private NativeGuestDispatcher() {}

    public static String buildCommand(File rootDir, String guestExecutable) {
        String box64Command = rootDir + "/usr/local/bin/box64 " + guestExecutable;
        if (guestExecutable == null || guestExecutable.isEmpty()) return box64Command;

        try {
            int machine = readPEMachine(new File(guestExecutable));
            File nativeWine = new File(rootDir, "/usr/local/bin/wine-arm64");

            if (machine == PE_ARM64 && nativeWine.isFile() && nativeWine.canExecute()) {
                return nativeWine.getPath() + " " + guestExecutable;
            }

            // Explicitly retain existing compatibility behavior for x86/x64
            // and for ARM64 when the native runtime is not installed.
            if (machine == PE_X86 || machine == PE_X64 || machine == PE_ARM64) {
                return box64Command;
            }
        }
        catch (IOException ignored) {
            // Preserve the old launcher behavior if the PE cannot be inspected.
        }

        return box64Command;
    }

    /** Returns the IMAGE_FILE_HEADER.Machine value, or -1 for a non-PE file. */
    public static int readPEMachine(File file) throws IOException {
        try (FileInputStream in = new FileInputStream(file)) {
            byte[] dos = new byte[64];
            if (readFully(in, dos) != dos.length || dos[0] != 'M' || dos[1] != 'Z') return -1;

            int peOffset = le32(dos, 0x3C);
            if (peOffset < 0 || peOffset > 64 * 1024 * 1024) return -1;

            long skipped = in.skip(peOffset - 64L);
            if (skipped != peOffset - 64L) {
                long remaining = peOffset - 64L - skipped;
                while (remaining > 0) {
                    long n = in.skip(remaining);
                    if (n <= 0) return -1;
                    remaining -= n;
                }
            }

            byte[] header = new byte[6];
            if (readFully(in, header) != header.length) return -1;
            if (header[0] != 'P' || header[1] != 'E' || header[2] != 0 || header[3] != 0) return -1;
            return (header[4] & 0xFF) | ((header[5] & 0xFF) << 8);
        }
    }

    private static int le32(byte[] b, int off) {
        return (b[off] & 0xFF)
            | ((b[off + 1] & 0xFF) << 8)
            | ((b[off + 2] & 0xFF) << 16)
            | ((b[off + 3] & 0xFF) << 24);
    }

    private static int readFully(FileInputStream in, byte[] buffer) throws IOException {
        int total = 0;
        while (total < buffer.length) {
            int n = in.read(buffer, total, buffer.length - total);
            if (n < 0) break;
            total += n;
        }
        return total;
    }
}
