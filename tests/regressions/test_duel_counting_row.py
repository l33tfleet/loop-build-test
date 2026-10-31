"""#118: a true-scale row of the smaller planet's circles spans the larger planet's width."""
import itertools
import json
import math
import re
from hashlib import sha256
from pathlib import Path

import pytest

DATA = json.loads(Path("data/planets.json").read_text(encoding="utf-8"))
DIAMETERS = {p["name"].lower(): p["diameter_km"] for p in DATA["planets"]}
PAIRS = list(itertools.permutations(DIAMETERS, 2))
PLURALS = {"mars": "Marses", "venus": "Venuses", "uranus": "Uranuses"}
BASE = "http://arcade.test"

ROW = re.compile(r'<span class="duel-row" aria-hidden="true" style="--circle: ([\d.]+)%">(.*?)</span>\s*<p', re.DOTALL)
CIRCLE = '<span class="duel-row-circle"></span>'
CAPTION = re.compile(r'<p class="duel-row-caption">(.*?)</p>')
SENTENCE = re.compile(r"(\w+) is <strong>([\d.]+)</strong> times as wide as (\w+)\.")


def duel(client, left, right):
    html = client.get("/", params={"left": left, "right": right}).text
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


def row(section):
    match = ROW.search(section)
    assert match, section
    return float(match.group(1)), match.group(2).count(CIRCLE)


def rules(selector):
    css = Path("static/arcade.css").read_text(encoding="utf-8")
    match = re.search(re.escape(selector) + r" \{([^}]*)\}", css)
    assert match, f"{selector} rule missing"
    return match.group(1)


@pytest.mark.parametrize(("left", "right"), [("jupiter", "earth"), ("earth", "jupiter")])
def test_jupiter_and_earth_row(client, left, right):
    width, count = row(duel(client, left, right))
    assert count == 12
    assert width == pytest.approx(100 * 12756 / 142984, abs=0.0001)
    assert 100 / width - 11 == pytest.approx(0.2, abs=0.05), "the twelfth circle is cut to 0.2 of its width"


@pytest.mark.parametrize(("left", "right"), PAIRS)
def test_every_pair_uses_the_duel_diameters_with_no_floor(client, left, right):
    big, small = sorted((DIAMETERS[left], DIAMETERS[right]), reverse=True)
    width, count = row(duel(client, left, right))
    assert width == pytest.approx(100 * small / big, abs=0.0001)
    assert count == math.ceil(big / small)


@pytest.mark.parametrize(("left", "right"), PAIRS)
def test_caption_repeats_the_sentence_ratio(client, left, right):
    section = duel(client, left, right)
    big, ratio, small = SENTENCE.search(section).groups()
    plural = PLURALS.get(small.lower(), small + "s")
    assert CAPTION.findall(section) == [f"{ratio} {plural} across {big}"]


def test_default_caption_matches_the_work_order(client):
    assert CAPTION.findall(duel(client, "jupiter", "earth")) == ["11.2 Earths across Jupiter"]


@pytest.mark.parametrize(("left", "right"), [("venus", "jupiter"), ("mars", "earth"), ("uranus", "saturn")])
def test_caption_plural_reads_as_english_for_names_ending_in_s(client, left, right):
    caption = CAPTION.findall(duel(client, left, right))[0]
    assert caption.split()[1] == PLURALS[left]


@pytest.mark.parametrize(("left", "right"), PAIRS)
def test_swapping_sides_gives_the_same_row_under_the_larger_planet(client, left, right):
    there, back = duel(client, left, right), duel(client, right, left)
    assert ROW.search(there).group(0) == ROW.search(back).group(0)
    assert CAPTION.findall(there) == CAPTION.findall(back)
    column = 1 if DIAMETERS[left] > DIAMETERS[right] else 2
    assert f'<div class="duel-count" style="grid-column: {column}">' in there


@pytest.mark.parametrize("slug", DIAMETERS)
def test_same_planet_picks_show_no_row(client, slug):
    section = duel(client, slug, slug)
    assert "duel-row" not in section and "duel-count" not in section


def test_error_page_shows_no_row(client):
    section = duel(client, "pluto", "earth")
    assert "duel-row" not in section and "duel-count" not in section


def test_row_is_decorative_and_caption_is_real_text(client):
    section = duel(client, "jupiter", "earth")
    match = ROW.search(section)
    assert "across" not in match.group(0)
    assert re.fullmatch(rf"(\s*{re.escape(CIRCLE)})+\s*", match.group(2))
    count = section[section.index('class="duel-count"'):]
    assert count.index('class="duel-row"') < count.index('class="duel-row-caption"')


def test_row_css_clips_without_scrolling_or_animating():
    box = rules(".duel-row")
    assert "width: 100%" in box and "overflow: hidden" in box and "display: flex" in box
    circle = rules(".duel-row-circle")
    assert "flex: none" in circle and "width: var(--circle)" in circle
    assert "aspect-ratio: 1" in circle and "border-radius: 50%" in circle
    for body in (box, circle, rules(".duel-row-caption"), rules(".duel-count")):
        assert "animation" not in body and "transition" not in body


@pytest.mark.parametrize(("left", "right", "whole"), [
    ("jupiter", "earth", 11), ("earth", "jupiter", 11), ("jupiter", "mercury", 29), ("venus", "earth", 1),
])
def test_row_in_a_390px_browser(client, left, right, whole):
    sync_api = pytest.importorskip("playwright.sync_api")

    def serve(route):
        response = client.get(route.request.url[len(BASE):])
        route.fulfill(status=response.status_code, body=response.content,
                      content_type=response.headers.get("content-type"))

    measure = """() => {
      const box = (node) => node.getBoundingClientRect();
      const portraits = [...document.querySelectorAll(".duel-portrait")];
      const big = portraits.reduce((a, b) => (box(a).width >= box(b).width ? a : b));
      const row = document.querySelector(".duel-row");
      const circles = [...row.querySelectorAll(".duel-row-circle")];
      const end = box(row).right;
      return {
        bigLeft: box(big).left, bigWidth: box(big).width, rowLeft: box(row).left, rowWidth: box(row).width,
        bottoms: portraits.map((p) => box(p).bottom), rowTop: box(row).top,
        circleWidth: box(circles[0]).width, circleHeight: box(circles[0]).height,
        whole: circles.filter((c) => box(c).right <= end + 0.01).length,
        last: (end - box(circles[circles.length - 1]).left) / box(circles[0]).width,
        scroll: document.documentElement.scrollWidth, wide: window.innerWidth,
      };
    }"""
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.route("**/*", serve)
            page.goto(f"{BASE}/?left={left}&right={right}")
            got = page.evaluate(measure)
        finally:
            browser.close()
    assert got["rowWidth"] == pytest.approx(got["bigWidth"], abs=0.5)
    assert got["rowLeft"] == pytest.approx(got["bigLeft"], abs=0.5)
    assert got["bottoms"][0] == pytest.approx(got["bottoms"][1], abs=0.5), "portraits keep their shared baseline"
    assert got["rowTop"] > max(got["bottoms"]), "the row sits under the portraits"
    assert got["circleHeight"] == pytest.approx(got["circleWidth"], abs=0.1), "circles stay round"
    assert got["whole"] == whole
    ratio = max(DIAMETERS[left], DIAMETERS[right]) / min(DIAMETERS[left], DIAMETERS[right])
    assert got["last"] == pytest.approx(ratio - whole, abs=0.1)
    assert got["scroll"] <= got["wide"]


# Replaces the digest pins in test_scale_helpers_109.py and test_duel_parameter_ownership_112.py: same pages and
# digests, so everything on the page except the new block stays byte-for-byte what those tests pinned.
COUNT_BLOCK = re.compile(r'\n *\n *<div class="duel-count".*?</div>\n *(?=\n)', re.DOTALL)


@pytest.mark.parametrize(("url", "status", "blocks", "digest"), [
    ("/", 200, 1, "8a3828c60cf98b247ef920341a0b49347a756f13e6284047320accb8eefc2d4f"),
    ("/?left=mars&right=neptune", 200, 1, "b40575cda9a95d103dbe420300255d1a58c2367d0cb84c1d1e21ffa20687982b"),
    ("/?left=mars&right=earth", 200, 1, "d2d635e5603c175605df376f27a26f04f69236a513ad6b7c19430ca2399e29ec"),
    ("/?round=1&choice=earth", 200, 1, "0848700c8eef150b43c93e2163d873ba84caba8f011bd05baf2ffbcaacad2465"),
    ("/?left=pluto", 422, 0, "66553c68e4b191a5e080fedb98374bc297b1e9c80fff6d6b2da929f4a7a8adb5"),
])
def test_page_is_unchanged_apart_from_the_row(client, url, status, blocks, digest):
    response = client.get(url)
    assert response.status_code == status
    rest, found = COUNT_BLOCK.subn("", response.text)
    assert found == blocks
    assert sha256(rest.encode()).hexdigest() == digest
