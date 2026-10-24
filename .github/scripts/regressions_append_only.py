"""Existing regression tests are append-only: never modified, renamed or deleted.

One exception lets the spec change. A `Supersedes: PATH::TEST` line in the PR's Issue names a top-level test that may
be replaced. The factory writes that line there only after its cross-vendor review approved the replacement as
required by the work order and at least as strict. Everything else in an existing file must survive unchanged (moved
is fine), and added code may not rebind a name the kept code binds. The labeler separately holds any net loss of
asserts.

Usage: regressions_append_only.py BASE_SHA ISSUE_BODY_FILE
"""
import ast
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

DIR = "tests/regressions/"
SUPERSEDES = re.compile(r"^Supersedes: (\S+\.py)::(\w+)", re.MULTILINE)


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def bound(node):
    """The top-level names a statement binds (a def, a class, an assignment, an import, or any of them nested in it)."""
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return {node.name}
    names = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store):
            names.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(n.name)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            names |= {a.asname or a.name.split(".")[0] for a in n.names}
    return names


def file_problems(path, base_src, head_src, superseded):
    """Every top-level statement of the base file survives in head, except the superseded tests, and nothing added
    rebinds a name the surviving statements bind (a later `def test_x` would replace the one pytest collects)."""
    try:
        head = ast.parse(head_src).body
    except SyntaxError as e:
        return [f"{path}: doesn't parse ({e})"]
    base = ast.parse(base_src).body
    tests = {n.name for n in base if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name.startswith("test")}
    out = [f"{path}: Supersedes names `{t}`, which isn't a top-level test here" for t in sorted(superseded - tests)]
    kept = [n for n in base if not (isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name in superseded)]
    left = Counter(ast.dump(n) for n in head)
    for node in kept:
        if left[ast.dump(node)] > 0:
            left[ast.dump(node)] -= 1
        else:
            name = getattr(node, "name", None) or ast.unparse(node).splitlines()[0][:60]
            out.append(f"{path}: changed or removed `{name}`" + ("" if superseded else " (no Supersedes line)"))
    protected = set().union(*map(bound, kept))
    for node in head:
        if left[ast.dump(node)] > 0:                     # added, not one of the kept statements
            left[ast.dump(node)] -= 1
            out += [f"{path}: added code rebinds `{name}`" for name in sorted(bound(node) & protected)]
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
