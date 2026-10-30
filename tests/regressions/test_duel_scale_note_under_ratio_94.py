import re

import pytest

NOTE = "Drawn to scale for this pair only: the larger planet always fills the same circle."
BUTTON = '<button type="submit">Compare</button>'
RATIO = '<p class="duel-ratio" aria-live="polite">'
NOTE_TAG = f'<p class="duel-scale-note">{NOTE}</p>'
PORTRAITS = '<div class="duel-portraits">'


def duel(html):
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


@pytest.mark.parametrize(("left", "right", "sentence"), [
    ("saturn", "mercury", "Saturn is <strong>24.7</strong> times as wide as Mercury."),
    ("mercury", "saturn", "Saturn is <strong>24.7</strong> times as wide as Mercury."),
    ("earth", "earth", "Both picks are Earth, so they are <strong>exactly the same size</strong>."),
])
def test_scale_note_directly_under_ratio_before_portraits(client, left, right, sentence):
    section = duel(client.get("/", params={"left": left, "right": right}).text)
    button = section.index(BUTTON)
    ratio = section.index(RATIO)
    note = section.index(NOTE_TAG)
    portraits = section.index(PORTRAITS)
    assert button < ratio < note < portraits
    assert section[button + len(BUTTON):ratio].strip() == "</form>"
    ratio_end = section.index("</p>", ratio) + len("</p>")
    assert section[ratio:ratio_end] == f"{RATIO}{sentence}</p>"
    assert section[ratio_end:note].strip() == ""
    assert section[note + len(NOTE_TAG):portraits].strip() == ""
    assert section.count('class="duel-ratio"') == 1
    assert section.count("duel-scale-note") == 1


def test_error_path_still_has_no_ratio_or_note(client):
    section = duel(client.get("/", params={"left": "pluto", "right": "earth"}).text)
    assert 'id="duel-error"' in section
    assert "duel-ratio" not in section
    assert "duel-scale-note" not in section
    assert "duel-portraits" not in section


def test_rocky_inset_caption_does_not_claim_earth_fills_panel(client):
    html = client.get("/").text
    match = re.search(r'<p class="inset-note">(.*?)</p>', html, re.DOTALL)
    assert match, "rocky inset caption missing"
    caption = match.group(1)
    assert "panel width" not in caption
    assert "fills the panel" not in caption
    assert "Different scale from the chart above" in caption
    assert "12,756 km" in caption
    assert "relative to Earth" in caption
