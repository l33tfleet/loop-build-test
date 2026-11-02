import re

import pytest  # noqa: F401

NOTE = "Drawn to scale for this pair only: the larger planet always fills the same circle."
BUTTON = '<button type="submit">Compare</button>'
RATIO = '<p class="duel-ratio" aria-live="polite">'
NOTE_TAG = f'<p class="duel-scale-note">{NOTE}</p>'
PORTRAITS = '<div class="duel-portraits">'


def duel(html):
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


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
