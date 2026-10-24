"""Existing regression tests are append-only: never modified, renamed or deleted.

One exception lets the spec change. A `Supersedes: PATH::TEST` line in the PR's Issue names a top-level test that may
be replaced. The factory writes that line there only after its cross-vendor review approved the replacement as
required by the work order and at least as strict. Everything else in an existing file must survive unchanged (moved
is fine). The labeler separately holds any net loss of asserts.

Usage: regressions_append_only.py BASE_SHA ISSUE_BODY_FILE
"""
import ast, re, subprocess, sys
from collections import Counter

DIR = "tests/regressions/"


def git(*args):
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def problems(base, issue_body):
    allowed = set(re.findall(r"^Supersedes: (\S+\.py)::(\w+)", issue_body, re.MULTILINE))
    out = []
    for line in git("diff", "--name-status", "--no-renames", base, "HEAD", "--", DIR).splitlines():
        status, path = line.split("\t", 1)
        if status == "A":
            continue
        if status != "M" or not path.endswith(".py"):
            out.append(f"{path}: {'deleted or renamed' if status == 'D' else 'changed'}")
            continue
        try:
            head = Counter(ast.dump(n) for n in ast.parse(git("show", f"HEAD:{path}")).body)
        except SyntaxError as e:
            out.append(f"{path}: doesn't parse ({e})")
            continue
        for node in ast.parse(git("show", f"{base}:{path}")).body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (path, node.name) in allowed:
                continue
            if head[ast.dump(node)] > 0:
                head[ast.dump(node)] -= 1
            else:
                name = getattr(node, "name", None) or ast.unparse(node).splitlines()[0][:60]
                out.append(f"{path}: changed or removed `{name}`" + ("" if allowed else " (no Supersedes line)"))
    return out


if __name__ == "__main__":
    bad = problems(sys.argv[1], open(sys.argv[2]).read())
    if bad:
        print("Append-only violation:\n" + "\n".join(bad))
        sys.exit(1)
    print("Regression tests: append-only (superseded: "
          + (", ".join(sorted(f"{p}::{t}" for p, t in set(re.findall(r"^Supersedes: (\S+\.py)::(\w+)",
                                                                       open(sys.argv[2]).read(), re.M)))) or "none")
          + ")")
