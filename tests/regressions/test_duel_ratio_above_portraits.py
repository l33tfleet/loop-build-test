import re
from pathlib import Path

import pytest  # noqa: F401 -- preserved under the append-only supersession policy

NOTE = "Drawn to scale for this pair only: the larger planet always fills the same circle."
BUTTON = '<button type="submit">Compare</button>'


def duel(html):
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


def test_error_path_has_no_ratio_or_caption(client):
    section = duel(client.get("/", params={"left": "pluto", "right": "earth"}).text)
    assert 'id="duel-error"' in section
    assert "duel-ratio" not in section
    assert "duel-scale-note" not in section


def test_scale_note_styled_like_quiz_note():
    css = Path("static/arcade.css").read_text(encoding="utf-8")
    quiz = re.search(r"\.quiz-scale-note \{([^}]*)\}", css).group(1)
    note = re.search(r"\.duel-scale-note \{([^}]*)\}", css)
    assert note, ".duel-scale-note rule missing"
    for decl in ("color: var(--muted)", "font-size: 0.9rem"):
        assert decl in quiz and decl in note.group(1)

