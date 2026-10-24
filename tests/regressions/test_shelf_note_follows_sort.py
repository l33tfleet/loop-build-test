import re

import pytest


@pytest.mark.parametrize("sort,note", [
    ("sun", "In order from the Sun"),
    ("diameter", "Largest diameter first"),
    ("year", "Shortest year first"),
    ("unknown", "In order from the Sun"),
])
def test_shelf_note_describes_current_order(client, sort, note):
    html = client.get("/", params={"sort": sort}).text
    shelf = re.search(r'<section class="planet-shelf"[^>]*>(.*?)</section>', html, re.DOTALL).group(1)
    assert re.search(rf'<p class="shelf-note">\s*{note}\s*</p>', shelf)
    assert shelf.index('<h2 id="shelf-title"') < shelf.index('<div class="shelf">')
