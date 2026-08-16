package com.winlator.xenvironment.components;

import com.winlator.core.ProcessHelper;

import java.io.File;
import java.io.FileInputStream;
import java.io.IOException;

/** Architecture-aware guest launcher. */
public final class NativeGuestDispatcher {
    private static final int PE_ARM64 = 0xAA64;

    private NativeGuestDispatcher() {}

    public static String buildCommand(File rootDir, String guestExecutable) {
        File nativeWine = findNativeWine(rootDir);
        if (nativeWine != null) {
            String[] tokens = ProcessHelper.splitCommand(guestExecutable);
            StringBuilder command = new StringBuilder(nativeWine.getPath());
            for (int j = 0; j < tokens.length; j++) {
                if (j == 0 && (tokens[0].equals("wine") || tokens[0].endsWith("/wine"))) continue;
                command.append(' ').append(quoteIfNeeded(tokens[j]));
            }
            return command.toString();
        }

        return rootDir + "/usr/local/bin/box64 " + guestExecutable;
    }

    private static String quoteIfNeeded(String arg) {
        if (arg == null || arg.isEmpty()) return "\"\"";
        if (arg.contains(" ") && !arg.startsWith("\"") && !arg.startsWith("'")) {
            return "\"" + arg + "\"";
        }
        return arg;
    }

    /** Returns true only when the guest command contains a real native ARM64 PE (Machine 0xAA64). */
    public static boolean isNativeArm64(File rootDir, String guestExecutable) {
        if (guestExecutable == null || guestExecutable.isEmpty() || findNativeWine(rootDir) == null) return false;
        String[] tokens = ProcessHelper.splitCommand(guestExecutable);
        for (String token : tokens) {
            File candidate = resolvePath(rootDir, token);
            if (candidate == null) continue;
            try {
                if (readPEMachine(candidate) == PE_ARM64) return true;
            } catch (IOException ignored) {
                // Keep scanning.
            }
        }
        return false;
    }

    private static File findNativeWine(File rootDir) {
        File[] candidates = {
            new File(rootDir, "/usr/local/bin/wine-arm64"),
            new File(rootDir, "/usr/local/bin/wine"),
            new File(rootDir, "/usr/local/bin/wine64")
        };
        for (File candidate : candidates) {
            if (candidate.isFile()) {
                if (!candidate.canExecute()) candidate.setExecutable(true, false);
                return candidate;
            }
        }
        return null;
    }

    public static File resolvePath(File rootDir, String rawToken) {
        if (rawToken == null) return null;
        String token = stripQuotes(rawToken).trim();
        if (token.isEmpty()) return null;

        File f = new File(token);
        if (f.isFile()) return f;
        f = new File(rootDir, token);
        if (f.isFile()) return f;

        if (token.length() >= 3 && (token.charAt(0) == 'C' || token.charAt(0) == 'c') && token.charAt(1) == ':') {
            String rel = token.substring(2).replace('\\', '/');
            f = new File(rootDir, "home/xuser/.wine/drive_c" + (rel.startsWith("/") ? rel : "/" + rel));
            if (f.isFile()) return f;
        }
        if (token.length() >= 3 && (token.charAt(0) == 'D' || token.charAt(0) == 'd') && token.charAt(1) == ':') {
            String rel = token.substring(2).replace('\\', '/');
            f = new File(rootDir, "home/xuser/.wine/dosdevices/d:" + (rel.startsWith("/") ? rel : "/" + rel));
            if (f.isFile()) return f;
            f = new File("/storage/emulated/0/Download" + (rel.startsWith("/") ? rel : "/" + rel));
            if (f.isFile()) return f;
            f = new File("/sdcard/Download" + (rel.startsWith("/") ? rel : "/" + rel));
            if (f.isFile()) return f;
        }
        if (token.length() >= 3 && (token.charAt(0) == 'Z' || token.charAt(0) == 'z') && token.charAt(1) == ':') {
            String rel = token.substring(2).replace('\\', '/');
            f = new File(rootDir, rel);
            if (f.isFile()) return f;
        }
        return null;
    }

    private static String stripQuotes(String value) {
        if (value.length() >= 2 && value.charAt(0) == '"' && value.charAt(value.length() - 1) == '"') return value.substring(1, value.length() - 1);
        return value;
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
            return (header[4] & 0xFF) | ((header[5] & 0xFF) << 8);
        }
    }

    private static int le32(byte[] b, int off) {
        return (b[off] & 0xFF) | ((b[off + 1] & 0xFF) << 8) | ((b[off + 2] & 0xFF) << 16) | ((b[off + 3] & 0xFF) << 24);
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
