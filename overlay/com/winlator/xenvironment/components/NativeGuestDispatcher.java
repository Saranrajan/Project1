package com.winlator.xenvironment.components;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

/**
 * Architecture-aware guest launcher used by the Project1 overlay.
 * ARM64 Windows PE files use the native ARM64 Wine path only when the
 * container contains /usr/local/bin/wine-arm64. Otherwise Box64 is retained.
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
        }
        catch (IOException ignored) {
            // Preserve existing behavior if PE inspection is unavailable.
        }

        return box64Command;
    }

    public static int readPEMachine(File file) throws IOException {
        try (FileInputStream in = new FileInputStream(file)) {
            byte[] dos = new byte[64];
            if (readFully(in, dos) != dos.length || dos[0] != 'M' || dos[1] != 'Z') return -1;
            int peOffset = le32(dos, 0x3C);
            if (peOffset < 64 || peOffset > 64 * 1024 * 1024) return -1;

            long remaining = peOffset - 64L;
            while (remaining > 0) {
                long n = in.skip(remaining);
                if (n <= 0) return -1;
                remaining -= n;
            }

            byte[] header = new byte[6];
            if (readFully(in, header) != header.length) return -1;
            if (header[0] != 'P' || header[1] != 'E' || header[2] != 0 || header[3] != 0) return -1;
            int machine = (header[4] & 0xFF) | ((header[5] & 0xFF) << 8);
            if (machine == PE_ARM64 || machine == PE_X86 || machine == PE_X64) return machine;
            return machine;
        }
    }

    private static int le32(byte[] b, int off) {
        return (b[off] & 0xFF) |
                ((b[off + 1] & 0xFF) << 8) |
                ((b[off + 2] & 0xFF) << 16) |
                ((b[off + 3] & 0xFF) << 24);
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
