"""#56: tapping a home page control updates its section in place instead of jumping to the top."""
import re

SCRIPT = re.compile(r'<script\b[^>]*\bsrc="(/static/[\w-]+\.js)"[^>]*>\s*</script>')
REGIONS = ("planet-duel", "planet-quiz", "birthday-booth", "shelf-sort", "planet-shelf")


def _script(client):
    html = client.get("/").text
    tag = SCRIPT.search(html)
    assert tag, "home page loads no local script"
    assert " defer" in tag.group() or " type=\"module\"" in tag.group()
    response = client.get(tag.group(1))
    assert response.status_code == 200
    return response.text


def test_page_loads_local_script_without_inline_code(client):
    html = client.get("/").text
    assert "<script>" not in html
    assert not re.search(r'<script\b[^>]*src="(https?:)?//', html)
    _script(client)


def test_every_reloading_control_sits_in_a_named_region(client):
    html = client.get("/").text
    ids = re.findall(r'data-region="([\w-]+)"', html)
    assert sorted(ids) == sorted(REGIONS)
    for name in REGIONS:
        match = re.search(rf'<(section|form)\b[^>]*data-region="{name}"[^>]*>(.*?)</\1>', html, re.DOTALL)
        assert match, f"region {name} missing"
    # Every GET form and query link on the page is inside one of the regions.
    stripped = re.sub(r'<(section|form)\b[^>]*data-region="[\w-]+".*?</\1>', "", html, flags=re.DOTALL)
    assert not re.search(r'<form\b', stripped)
    assert not re.search(r'href="/\?', stripped)


def test_region_keeps_attributes_tests_pin(client):
    html = client.get("/").text
    assert re.search(r'<form\b[^>]*action="/"[^>]*method="get"', html)
    assert 'href="/?age=10"' in html


def test_script_swaps_regions_and_keeps_the_tapped_section_still(client):
    js = _script(client)
    assert "preventDefault" in js
    assert re.search(r"\bfetch\(", js)
    assert "DOMParser" in js
    assert "data-region" in js
    assert "replaceWith" in js
    # Keeps the visitor where they tapped: measures the section before and after, then scrolls by the difference.
    assert "getBoundingClientRect" in js and "scrollBy" in js
    # The URL still reflects the state so reload, share and back keep working.
    assert "pushState" in js and "popstate" in js
    # Falls back to a normal navigation if the fetch fails.
    assert re.search(r"location\.(assign|href)", js)


def test_script_is_offline_only(client):
    js = _script(client)
    assert not re.search(r"https?://", js)
