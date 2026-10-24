import re
from pathlib import Path

import pytest

FACTORY_DIR = Path(__file__).resolve().parents[2] / ".factory"


@pytest.mark.parametrize("filename", ["priorities.md", "personas.md"])
def test_factory_guidance_files_exist(filename):
    assert (FACTORY_DIR / filename).is_file()


def test_factory_personas_start_with_pages():
    assert (FACTORY_DIR / "personas.md").read_text().startswith("Pages: /\n")


def test_factory_priorities_have_numbered_list():
    priorities = (FACTORY_DIR / "priorities.md").read_text()
    assert re.findall(r"^(\d+)\. \S", priorities, re.MULTILINE) == ["1", "2", "3", "4"]
