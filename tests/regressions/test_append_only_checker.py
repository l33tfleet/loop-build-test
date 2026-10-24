import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("checker", ROOT / ".github" / "scripts" / "regressions_append_only.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)

PATH = "tests/regressions/test_x.py"
BASE = '''import re

LIMIT = 10


def helper(v):
    return v * 2


def test_large():
    assert helper(3) == 6


def test_other():
    assert LIMIT == 10
'''
REPLACED = BASE.replace("def test_large():\n    assert helper(3) == 6\n",
                        "def test_true_scale():\n    assert helper(3) == 6\n    assert helper(0) == 0\n")


def problems(head, superseded=frozenset()):
    return checker.file_problems(PATH, BASE, head, set(superseded))


REMOVED = BASE.replace("def test_large():\n    assert helper(3) == 6\n\n\n", "")
NOT_REMOVED = f"{PATH}: changed beyond removing nothing (no Supersedes line)"
ONLY_REMOVE = f"{PATH}: changed beyond removing `test_large` (only the superseded tests may be removed; put replacements in a new file)"


def test_unchanged_passes():
    assert problems(BASE) == []


def test_removing_the_superseded_test_passes():
    assert problems(REMOVED, {"test_large"}) == []


@pytest.mark.parametrize("head", [REMOVED, REPLACED, BASE + "\n\ndef test_more():\n    assert True\n",
                                  BASE.replace("LIMIT = 10\n", "") + "\nLIMIT = 10\n"])
def test_any_change_without_supersedes_fails(head):
    assert problems(head) == [NOT_REMOVED]


def test_a_line_naming_another_test_fails():
    assert problems(REMOVED, {"test_other"}) == [ONLY_REMOVE.replace("`test_large`", "`test_other`")]


@pytest.mark.parametrize("name", ["helper", "LIMIT", "test_missing"])
def test_supersedes_only_covers_an_existing_top_level_test(name):
    assert f"{PATH}: Supersedes names `{name}`, which isn't a top-level test here" in problems(BASE, {name})


@pytest.mark.parametrize("added", [
    "def test_true_scale():\n    assert helper(3) == 6\n",
    "def test_other():\n    assert True\n",
    "def helper(v):\n    return 6\n",
    "del test_other\n",
    "try:\n    raise ValueError\nexcept ValueError as test_other:\n    pass\n",
    "X = globals().pop('test_other')\n",
])
def test_nothing_may_be_added_to_an_existing_file(added):
    assert problems(REMOVED + "\n\n" + added, {"test_large"}) == [ONLY_REMOVE]


def test_weakening_a_helper_fails_even_with_supersedes():
    assert problems(REMOVED.replace("return v * 2", "return 6"), {"test_large"}) == [ONLY_REMOVE]


def test_unparseable_head_fails():
    assert problems("def (:\n") == [f"{PATH}: doesn't parse (invalid syntax (<unknown>, line 1))"]


def test_deleting_or_renaming_a_regression_file_fails(tmp_path, monkeypatch):
    def git(*args):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *args], cwd=tmp_path, check=True,
                       capture_output=True)
    (tmp_path / "tests" / "regressions").mkdir(parents=True)
    (tmp_path / PATH).write_text(BASE)
    git("init", "-q")
    git("add", ".")
    git("commit", "-qm", "base")
    git("mv", PATH, "tests/regressions/test_y.py")
    git("commit", "-qm", "rename")
    monkeypatch.chdir(tmp_path)
    base = subprocess.run(["git", "rev-parse", "HEAD~1"], cwd=tmp_path, capture_output=True, text=True,
                          check=True).stdout.strip()
    assert checker.problems(base, set()) == [f"{PATH}: deleted or renamed"]
