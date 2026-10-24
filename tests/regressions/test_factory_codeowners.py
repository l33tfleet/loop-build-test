from pathlib import Path


def test_factory_directory_requires_code_owner():
    root = Path(__file__).resolve().parents[2]
    entries = [
        line.split()
        for line in (root / ".github" / "CODEOWNERS").read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]

    github_index = entries.index(["/.github/", "@k7lim"])
    assert entries[github_index + 1] == ["/.factory/", "@k7lim"]
