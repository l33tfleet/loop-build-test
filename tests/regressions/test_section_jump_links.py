import re
from html import unescape
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"
NAV = re.compile(r'<nav aria-label="Sections"[^>]*>(.*?)</nav>', re.DOTALL)
LINK = re.compile(r'<a\b[^>]*href="#([^"]+)"[^>]*>(.*?)</a>', re.DOTALL)
LABELS = ["Duel", "Quiz", "Birthdays", "Scale", "Rocky planets", "Planets"]
TEXT_COLOURS = {"var(--paper)", "var(--ink)", "var(--muted)"}


def _links(html):
    nav = NAV.search(html)
    assert nav, "no <nav aria-label=\"Sections\">"
    return [(target, " ".join(unescape(re.sub(r"<[^>]+>", "", text)).split()))
            for target, text in LINK.findall(nav.group(1))]


def _rule(css, selector):
    match = re.search(rf"(?:^|}}|\n){re.escape(selector)}\s*\{{([^}}]*)\}}", css)
    assert match, f"no CSS rule for {selector}"
    return match.group(1)


def test_sections_nav_sits_right_under_the_header(client):
    html = client.get("/").text
    after_header = html.split("</header>", 1)[1]
    assert after_header.lstrip().startswith('<nav aria-label="Sections"')
    assert after_header.find("<nav") < after_header.find("<main>")


def test_sections_nav_has_six_labelled_links_in_page_order(client):
    html = client.get("/").text
    links = _links(html)
    assert [label for _, label in links] == LABELS
    spots = [html.find(f'id="{target}"') for target, _ in links]
    assert all(spot >= 0 for spot in spots), links
    assert spots == sorted(spots)
    assert len(set(spots)) == 6


def test_each_link_targets_a_section_heading_or_region(client):
    html = client.get("/").text
    for target, _ in _links(html):
        element = re.search(rf'<(\w+)\b[^>]*\bid="{re.escape(target)}"', html).group(1)
        assert element in {"h2", "h3", "section"}, (target, element)
        # A heading's section names it, so the jump lands on that part of the page.
        assert f'aria-labelledby="{target}"' in html or element == "section"


def test_jump_links_are_plain_in_page_anchors_outside_script_regions(client):
    html = client.get("/").text
    nav = NAV.search(html).group(0)
    assert "data-region" not in nav
    assert all(href.startswith("#") for href in re.findall(r'href="([^"]*)"', nav))


def test_jump_links_wrap_with_tall_tap_targets_and_page_text_colours():
    css = CSS.read_text()
    row = _rule(css, ".section-nav ul")
    assert re.search(r"display:\s*flex", row) and re.search(r"flex-wrap:\s*wrap", row)
    link = _rule(css, ".section-nav a")
    height = re.search(r"min-height:\s*(\d+)px", link)
    assert height and int(height.group(1)) >= 44
    assert re.search(r"display:\s*(inline-)?flex", link)
    colours = set(re.findall(r"(?<![-\w])color:\s*([^;]+);", link))
    assert colours and colours <= TEXT_COLOURS, colours


def test_jump_links_use_the_section_nav_class(client):
    html = client.get("/").text
    assert re.search(r'<nav aria-label="Sections" class="section-nav">', html)
