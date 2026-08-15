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
    
    # 1. Look for Gradle 'What went wrong' block
    what_idx = -1
    for i, line in enumerate(lines):
        if "* What went wrong:" in line or "* what went wrong:" in line:
            what_idx = i
            
    if what_idx != -1:
        end_idx = min(total, what_idx + 40)
        for j in range(what_idx, min(total, what_idx + 60)):
            if "* Try:" in lines[j] or "* Get more help" in lines[j]:
                end_idx = j
                break
        wrong_excerpt = "\n".join(lines[what_idx:end_idx])
        print("\n" + "="*80)
        print("GRADLE 'WHAT WENT WRONG' SECTION:")
        print("="*80)
        print(wrong_excerpt)
        print("="*80 + "\n")
        
        summary = " ".join([l.strip() for l in lines[what_idx:end_idx] if l.strip()])
        if len(summary) > 1000:
            summary = summary[:997] + "..."
        escaped_summary = summary.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=Gradle Root Cause::{escaped_summary}")
        return

    # 2. If 'What went wrong' not found, search for 'Execution failed for task' or 'FAILURE:'
    fail_indices = []
    for i, line in enumerate(lines):
        if any(k in line for k in ["FAILURE: Build failed", "Execution failed for task", "FAILED", "Caused by:"]):
            fail_indices.append(i)
            
    if fail_indices:
        last_fail = fail_indices[-1]
        start = max(0, last_fail - 10)
        end = min(total, last_fail + 40)
        excerpt = "\n".join(lines[start:end])
        print("\n" + "="*80)
        print("GRADLE FAILURE TRACE:")
        print("="*80)
        print(excerpt)
        print("="*80 + "\n")
        summary = " ".join([l.strip() for l in lines[start:end] if l.strip()])[:997]
        escaped_summary = summary.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
        print(f"::error title=Gradle Failure Trace::{escaped_summary}")
        return

    # 3. Fallback: last 50 lines
    last_lines = lines[-50:]
    summary = " ".join([l.strip() for l in last_lines if l.strip()])[:997]
    escaped_summary = summary.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title=Gradle Build End::{escaped_summary}")

if __name__ == "__main__":
    main()
