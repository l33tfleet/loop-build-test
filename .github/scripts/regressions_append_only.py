"""Existing regression tests are append-only: never modified, renamed or deleted.

One exception lets the spec change. A `Supersedes: PATH::TEST` line in the PR's Issue names a top-level test that may
be replaced. The factory writes that line there only after its cross-vendor review approved the replacement as
required by the work order and at least as strict. The file may only lose that test; replacements go in a new
regression file, since any statement added to the old one could rebind or delete a test at import. The labeler
separately holds any net loss of asserts.

Usage: regressions_append_only.py BASE_SHA ISSUE_BODY_FILE
"""
import ast
import re
import subprocess
import sys
from pathlib import Path

DIR = "tests/regressions/"
SUPERSEDES = re.compile(r"^Supersedes: (\S+\.py)::(\w+)", re.MULTILINE)


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def file_problems(path, base_src, head_src, superseded):
    """An existing file may only lose its superseded tests: everything else stays exactly as it was, in order, and
    nothing is added (any added statement can rebind or delete a test at import). Replacements go in a new file."""
    try:
        head = [ast.dump(n) for n in ast.parse(head_src).body]
    except SyntaxError as e:
        return [f"{path}: doesn't parse ({e})"]
    base = ast.parse(base_src).body
    tests = {n.name for n in base if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")}
    out = [f"{path}: Supersedes names `{t}`, which isn't a top-level test here" for t in sorted(superseded - tests)]
    kept = [n for n in base if not (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in superseded)]
    if [ast.dump(n) for n in kept] != head:
        why = "only the superseded tests may be removed; put replacements in a new file" if superseded else \
              "no Supersedes line"
        out.append(f"{path}: changed beyond removing {', '.join(f'`{t}`' for t in sorted(superseded)) or 'nothing'}"
                   f" ({why})")
    return out


def problems(base, allowed):
    out = []
    for line in git("diff", "--name-status", "--no-renames", base, "HEAD", "--", DIR).splitlines():
        status, path = line.split("\t", 1)
        if status == "A":
            continue
        if status != "M" or not path.endswith(".py"):
            out.append(f"{path}: {'deleted or renamed' if status == 'D' else 'changed'}")
            continue
        out += file_problems(path, git("show", f"{base}:{path}"), git("show", f"HEAD:{path}"),
                             {t for p, t in allowed if p == path})
    return out


if __name__ == "__main__":
    allowed = set(SUPERSEDES.findall(Path(sys.argv[2]).read_text()))
    bad = problems(sys.argv[1], allowed)
    if bad:
        print("Append-only violation:\n" + "\n".join(bad))
        sys.exit(1)
    print(f"Regression tests: append-only (superseded: {', '.join(sorted(f'{p}::{t}' for p, t in allowed)) or 'none'})")
