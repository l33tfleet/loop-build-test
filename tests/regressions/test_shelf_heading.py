import re

SECTION = re.compile(r'<section class="planet-shelf"([^>]*)>(.*?)</section>', re.DOTALL)


def _shelf(client):
    match = SECTION.search(client.get("/").text)
    assert match, "planet shelf section missing"
    return match.group(1), match.group(2)


def test_shelf_section_is_labelled_by_visible_heading(client):
    attrs, body = _shelf(client)
    assert 'aria-label=' not in attrs
    label_id = re.search(r'aria-labelledby="([^"]+)"', attrs).group(1)
    heading = re.search(rf'<h2 id="{re.escape(label_id)}"[^>]*>(.*?)</h2>', body, re.DOTALL)
    assert heading and heading.group(1).strip() == "The eight planets"
    assert re.search(r'<p class="shelf-note">\s*In order from the Sun\s*</p>', body)


def test_heading_styled_like_other_section_titles(client):
    css = client.get("/static/arcade.css").text
    rule = re.search(r"\.planet-shelf > h2\s*\{([^}]*)\}", css)
    assert rule and "color: var(--paper)" in rule.group(1)
