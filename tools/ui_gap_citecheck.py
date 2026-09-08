"""Report UI_GAP citations that no longer land on real code.

Usage: python3 citecheck.py [worktree]   (default: cwd)
Exit 1 if any citation is past end of file or lands on a blank/closing line.
"""
import os, re, sys

root = sys.argv[1] if len(sys.argv) > 1 else os.getcwd()
gap = open(os.path.join(root, "doc/chat-first/UI_GAP.md")).read()
cites = sorted(set(re.findall(r"(?:web/src/)?([a-z]+\.(?:ts|css)):(\d+)", gap)))

DEAD = {"", "}", "};", ")", "});"}
bad = []
for name, ln in cites:
    path = os.path.join(root, "web/src", name)
    if not os.path.exists(path):
        bad.append((name, ln, "NO SUCH FILE"))
        continue
    lines = open(path).read().split("\n")
    n = int(ln)
    if n > len(lines):
        bad.append((name, ln, f"PAST EOF ({len(lines)} lines)"))
    elif lines[n - 1].strip() in DEAD:
        bad.append((name, ln, f"lands on {lines[n-1].strip()!r}"))

print(f"{len(cites)} unique citations, {len(cites)-len(bad)} good, {len(bad)} stale")
for b in bad:
    print(f"  {b[0]}:{b[1]}  {b[2]}")
sys.exit(1 if bad else 0)
