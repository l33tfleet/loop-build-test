import re
from pathlib import Path

import pytest

NOTE = "Drawn to scale for this pair only: the larger planet always fills the same circle."
BUTTON = '<button type="submit">Compare</button>'


def duel(html):
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


@pytest.mark.parametrize(("left", "right", "sentence"), [
    ("saturn", "mercury", "Saturn is <strong>24.7</strong> times as wide as Mercury."),
    ("mercury", "saturn", "Saturn is <strong>24.7</strong> times as wide as Mercury."),
    ("earth", "earth", "Both picks are Earth, so they are <strong>exactly the same size</strong>."),
])
def test_ratio_sits_right_under_compare_and_caption_under_portraits(client, left, right, sentence):
    section = duel(client.get("/", params={"left": left, "right": right}).text)
    button = section.index(BUTTON)
    ratio = section.index('<p class="duel-ratio" aria-live="polite">')
    portraits = section.index('<div class="duel-portraits">')
    note = section.index(f'<p class="duel-scale-note">{NOTE}</p>')
    assert button < ratio < portraits < note
    assert section[button + len(BUTTON):ratio].strip() == "</form>"
    assert sentence in section[ratio:portraits]
    assert section.count('class="duel-ratio"') == 1
    assert section.count("duel-scale-note") == 1
    closing = section.rindex("</div>", portraits, note)
    assert section[closing + len("</div>"):note].strip() == ""


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

