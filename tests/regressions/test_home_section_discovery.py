"""Work order #42: home page sections are discovered by convention, with no central list."""
import ast
import importlib
import sys
import types
from pathlib import Path

from fastapi.testclient import TestClient
from jinja2 import ChoiceLoader, FileSystemLoader

from app import main, sections

SECTIONS_DIR = Path(sections.__file__).parent
FIXTURE = '''
def context(state):
    return {"fixture_sort": state["sort"]}
'''


def _temp_package(tmp_path, name, files, *extra_paths):
    """A throwaway package whose modules live in tmp_path (plus any extra directories)."""
    pkg_dir = tmp_path / name
    pkg_dir.mkdir()
    for filename, source in files.items():
        (pkg_dir / filename).write_text(source)
    package = types.ModuleType(name)
    package.__path__ = [str(pkg_dir), *map(str, extra_paths)]
    sys.modules[name] = package
    return package


def test_discovery_iterates_the_package_in_filename_order(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "modules", dict(sys.modules))
    files = {
        "20_beta_thing.py": "def context(state):\n    return {'beta': state['n'] * 2}\n",
        "10_alpha.py": "def context(state):\n    return {'alpha': state['n']}\n",
        "_private.py": "raise AssertionError('helpers starting with _ are not sections')\n",
    }
    package = _temp_package(tmp_path, "fixture_sections_a", files)
    found = sections.discover(package)
    assert [s.template for s in found] == ["sections/10-alpha.html", "sections/20-beta-thing.html"]
    assert [s.context({"n": 3}) for s in found] == [{"alpha": 3}, {"beta": 6}]


def test_a_new_section_file_and_template_add_a_section_to_the_page(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "modules", dict(sys.modules))
    package = _temp_package(tmp_path, "fixture_sections_b", {"35_fixture_probe.py": FIXTURE}, SECTIONS_DIR)
    template_dir = tmp_path / "templates"
    (template_dir / "sections").mkdir(parents=True)
    (template_dir / "sections" / "35-fixture-probe.html").write_text(
        '<section class="fixture-probe">sorted by {{ fixture_sort }}</section>\n')
    env = main.templates.env
    monkeypatch.setattr(env, "loader", ChoiceLoader([FileSystemLoader(template_dir), env.loader]))
    monkeypatch.setattr(env, "cache", None)
    monkeypatch.setattr(main, "SECTIONS_PACKAGE", package)

    html = TestClient(main.app).get("/", params={"sort": "diameter"}).text
    assert '<section class="fixture-probe">sorted by diameter</section>' in html
    # Filename order decides placement: 35 lands between birthdays (30) and the diameter scale (40).
    assert html.index('class="birthday-booth"') < html.index("fixture-probe") < html.index('class="diameter-scale"')
    assert html.count('class="planet-duel"') == 1 and html.count('class="planet-shelf"') == 1


def test_every_section_module_has_a_template_and_a_context():
    found = sections.discover()
    assert len(found) >= 6
    templates_dir = Path(main.ROOT) / "templates"
    for section in found:
        assert (templates_dir / section.template).is_file(), section.template
        assert callable(section.context)
    stems = sorted(p.stem for p in SECTIONS_DIR.glob("[0-9]*.py"))
    assert [s.template for s in found] == [f"sections/{s.replace('_', '-')}.html" for s in stems]


def test_no_section_module_imports_another_section():
    for path in SECTIONS_DIR.glob("[0-9]*.py"):
        for node in ast.walk(ast.parse(path.read_text())):
            if isinstance(node, ast.ImportFrom):
                assert node.level == 0, f"{path.name} uses a relative import"
                names = [node.module or ""] + [f"{node.module}.{a.name}" for a in node.names]
            elif isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            else:
                continue
            assert not any(n == "app.sections" or n.startswith("app.sections.") for n in names), path.name
            assert not any(n in ("app", "app.main") for n in names), path.name
        if (call := "import_module") in path.read_text():
            raise AssertionError(f"{path.name} calls {call}")


def test_home_only_builds_state_collects_sections_and_renders():
    source = Path(main.__file__).read_text()
    for section_word in ("_duel(", "_quiz(", "birthdays", "rocky", "QUIZ_PAIRS"):
        assert section_word not in source, section_word
    index = (Path(main.ROOT) / "templates" / "index.html").read_text()
    for section_class in ("planet-duel", "planet-quiz", "birthday-booth", "diameter-scale", "planet-shelf"):
        assert section_class not in index, section_class
    assert importlib.import_module("app.page_state")
