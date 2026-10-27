"""The shelf registry alone owns sort validation, presentation and ordering (#91)."""

import importlib
import re
from html import escape

from app import main, page_state

shelf = importlib.import_module("app.sections.60_planet_shelf")


def _assert_sort(client, name, entry):
    response = client.get("/", params={"sort": name, "age": "10"})
    assert response.status_code == 200
    html = response.text
    assert f'<p class="shelf-note">{escape(entry["note"])}</p>' in html
    assert f'<option value="{name}" selected>{escape(entry["label"])}</option>' in html
    assert f'<input type="hidden" name="sort" value="{name}">' in html
    return html


def test_every_registered_sort_renders_its_note(client):
    for name, entry in shelf.SORTS.items():
        _assert_sort(client, name, entry)


def test_adding_one_registry_entry_is_enough(client, monkeypatch):
    entry = {
        "label": "Longest year first",
        "note": "From the longest orbit to the shortest",
        "key": lambda planet, state: (-state["periods"][planet["name"]], planet["name"].lower()),
    }
    monkeypatch.setitem(shelf.SORTS, "longest-year", entry)
    html = _assert_sort(client, "longest-year", entry)
    cards = re.findall(r'<article class="planet-card"[^>]*>\s*<h2>([^<]+)</h2>', html)
    assert cards == ["Neptune", "Uranus", "Saturn", "Jupiter", "Mars", "Earth", "Venus", "Mercury"]
    options = re.findall(r'<option value="([^"]+)"(?: selected)?>', html)
    assert options == list(shelf.SORTS)


def test_missing_and_invalid_sort_default_to_first_registry_entry(client, monkeypatch):
    entry = {"label": "Reverse Sun order", "note": "Outer planets first",
             "key": lambda planet, state: (-planet["order"], planet["name"].lower())}
    monkeypatch.setattr(shelf, "SORTS", {"outer-first": entry, **shelf.SORTS})
    expected = _assert_sort(client, "outer-first", entry)
    for params in ({"age": "10"}, {"sort": "unknown", "age": "10"}, {"sort": "", "age": "10"}):
        response = client.get("/", params=params)
        assert response.status_code == 200
        assert response.text == expected


def test_shared_state_keeps_raw_sort_for_sections():
    assert not hasattr(page_state, "SORT_KEYS")
    state = page_state.build({"sort": "future-sort"}, main.SNAPSHOT, main.ORBITAL_PERIOD_DAYS)
    assert state["sort"] == "future-sort"
