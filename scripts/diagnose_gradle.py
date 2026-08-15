#!/usr/bin/env python3
import pathlib
import sys

def main():
    log_path = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else pathlib.Path("gradle-build.log")
    if not log_path.exists():
        print(f"::error::Log file {log_path} not found")
        sys.exit(1)
        
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    total = len(lines)
    print(f"Total gradle log lines: {total}")
    
    # 1. Search for 'FAILED: ' or 'error: ' (ignoring warnings and entering directory)
    failed_lines = []
    for i, line in enumerate(lines):
        if line.startswith("FAILED:") or "clang: error:" in line or "clang++: error:" in line or ("error:" in line and "warning:" not in line and "note:" not in line):
            failed_lines.append(i)
            
    if failed_lines:
        # Take from first failure to 30 lines after last failure
        start = max(0, failed_lines[0] - 2)
        end = min(total, failed_lines[-1] + 35)
        failure_block = "\n".join(lines[start:end])
        print("\n" + "="*80)
        print("EXACT COMPILER / BUILD FAILURE BLOCK:")
        print("="*80)
        print(failure_block)
        print("="*80 + "\n")
        
        # Format for github annotation
        summary = " ".join([l.strip() for l in lines[failed_lines[0]:min(total, failed_lines[0] + 25)] if l.strip()])
        if len(summary) > 1000:
            summary = summary[:997] + "..."
        escaped_summary = summary.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=Exact Compiler Error::{escaped_summary}")
        return

    # 2. Search for '* What went wrong:' and skip the argument dump to get to the error
    for i, line in enumerate(lines):
        if "* What went wrong:" in line or "* what went wrong:" in line:
            start = i
            end = min(total, i + 60)
            summary = " ".join([l.strip() for l in lines[start:end] if l.strip()])[:997]
            escaped_summary = summary.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
            print(f"::error title=Gradle Root Cause::{escaped_summary}")
            return

if __name__ == "__main__":
    main()
