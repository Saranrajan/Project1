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
    
    error_indices = []
    for i, line in enumerate(lines):
        l_lower = line.lower()
        if any(k in l_lower for k in ["* what went wrong:", "failure:", "error:", "exception:", "caused by:", "cmake error", "clang++: error:"]):
            error_indices.append(i)
            
    print(f"Found {len(error_indices)} error/failure markers.")
    
    # Collect unique lines around error indices
    selected_indices = set()
    for idx in error_indices[-20:]:  # Focus on the last 20 error markers
        for j in range(max(0, idx - 5), min(total, idx + 15)):
            selected_indices.add(j)
            
    # If no markers found, take the last 50 lines
    if not selected_indices:
        for j in range(max(0, total - 50), total):
            selected_indices.add(j)
            
    excerpt_lines = [lines[j] for j in sorted(selected_indices)]
    excerpt_text = "\n".join(excerpt_lines)
    
    print("\n" + "="*80)
    print("GRADLE BUILD FAILURE EXCERPT:")
    print("="*80)
    print(excerpt_text)
    print("="*80 + "\n")
    
    # Format single-line summary for GitHub Actions annotation (limit to 1000 chars)
    first_few = [l.strip() for l in excerpt_lines if l.strip()][:15]
    summary = " | ".join(first_few)
    if len(summary) > 1000:
        summary = summary[:997] + "..."
    # Escape newlines as %0A for GitHub Actions ::error
    escaped_summary = summary.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")
    print(f"::error title=Gradle Build Error::{escaped_summary}")

if __name__ == "__main__":
    main()
