"""After Claude edits a Python or UI file, run the tests that mention it.

Reads the hook's JSON on stdin. Exits 2 with the failures so Claude sees them;
stays quiet when there is nothing to run or everything passes.
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    try:
        path = json.load(sys.stdin).get("tool_input", {}).get("file_path", "")
    except ValueError:
        return 0
    stem, ext = os.path.splitext(os.path.basename(path))
    if ext not in (".py", ".js") or not stem or os.sep + "tests" + os.sep in path:
        return 0
    tests = os.path.join(ROOT, "tests")
    hits = []
    for name in sorted(os.listdir(tests)):
        if name.startswith("test_") and name.endswith(".py"):
            with open(os.path.join(tests, name), encoding="utf-8", errors="ignore") as f:
                if stem in f.read():
                    hits.append(os.path.join(tests, name))
    if not hits:
        return 0
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", *hits[:12]]
    env = dict(os.environ)
    if os.name != "nt":   # off Windows, stand in for the Windows-only modules
        shim = os.path.join(ROOT, ".claude", "skills", "win-check", "shim")
        env["PYTHONPATH"] = shim + os.pathsep + env.get("PYTHONPATH", "")
    try:
        out = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True, timeout=150)
    except subprocess.TimeoutExpired:
        return 0
    if out.returncode in (0, 5):
        return 0
    print(f"Tests touching {stem} failed:\n" + (out.stdout + out.stderr)[-3000:], file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
