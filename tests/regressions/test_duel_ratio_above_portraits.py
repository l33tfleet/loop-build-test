import re
from pathlib import Path  # noqa: F401

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

