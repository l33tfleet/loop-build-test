from pathlib import Path

CODEOWNERS = Path(__file__).resolve().parents[2] / ".github" / "CODEOWNERS"


def rules():
    return [line.split() for line in CODEOWNERS.read_text().splitlines() if line.strip() and not line.startswith("#")]


def test_test_configuration_and_gates_stay_owned():
    owned = {r[0] for r in rules() if len(r) > 1}
    assert {"conftest.py", "pyproject.toml", "/.github/", "/.factory/", "/Makefile", "/AGENTS.md"} <= owned


def test_ordinary_tests_are_not_owned():
    assert not [r for r in rules() if r[0].startswith(("/tests", "tests"))]
