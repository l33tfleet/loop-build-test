import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"
SECTION = re.compile(r'<section class="diameter-scale"[^>]*>(.*?)</section>', re.DOTALL)
HAS_BARS = ".diameter-scale:has(#scale-view-bars:checked)"


def _note(client, view):
    section = SECTION.search(client.get("/").text).group(1)
    notes = re.findall(r'<p class="scale-note" data-view="(\w+)"[^>]*>(.*?)</p>', section, re.DOTALL)
    assert [v for v, _ in notes] == ["circles", "bars"], notes
    return dict(notes)[view]


def _rules(css, selector):
    return " ".join(re.findall(re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", css))


def test_circles_note_describes_circle_diameter_against_jupiter(client):
    note = _note(client, "circles")
    assert "circle's diameter" in note and "Jupiter's 142,984 km" in note
    assert "bar" not in note.lower()


def test_bars_note_describes_bar_length_and_never_circles(client):
    note = _note(client, "bars")
    assert "bar's length" in note and "divided by Jupiter's 142,984 km" in note
    assert "circle" not in note.lower()


def test_only_the_checked_views_note_is_displayed():
    css = CSS.read_text()
    # display: none also drops the hidden note from the accessibility tree.
    assert re.search(r"display:\s*none", _rules(css, '.scale-note[data-view="bars"]'))
    assert re.search(r"display:\s*none", _rules(css, f'{HAS_BARS} .scale-note[data-view="circles"]'))
    assert re.search(r"display:\s*block", _rules(css, f'{HAS_BARS} .scale-note[data-view="bars"]'))
