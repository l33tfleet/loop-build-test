"""#122: a faint dashed Earth ring at the same scale, and a boxed 'Full circle = ...' callout."""
import itertools
import re
from hashlib import sha256  # noqa: F401

import pytest

DIAMETERS = {
    "mercury": 4879, "venus": 12104, "earth": 12756, "mars": 6792,
    "jupiter": 142984, "saturn": 120536, "uranus": 51118, "neptune": 49528,
}
NAMES = {slug: slug.capitalize() for slug in DIAMETERS}
EARTH = DIAMETERS["earth"]

BUTTON = '<button type="submit">Compare</button>'
RATIO = '<p class="duel-ratio" aria-live="polite">'
PORTRAITS = '<div class="duel-portraits">'
FRAME = re.compile(r'<span class="duel-frame" aria-hidden="true">(.*?)</span>\s*<figcaption>', re.DOTALL)
PORTRAIT = re.compile(r'<span class="duel-portrait" data-planet="(\w+)" style="width: ([\d.]+)%"></span>')
LABEL = '<span class="duel-earth-ring-label">Earth, same scale</span>'
# The label is nested in the ring so it is placed from the ring's own height, never on top of it.
RING = re.compile(r'<span class="duel-earth-ring" style="--ring: ([\d.]+)%">' + re.escape(LABEL) + "</span>")
BASE = "http://arcade.test"


def duel(client, **params):
    html = client.get("/", params=params).text
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


def frames(section):
    found = FRAME.findall(section)
    assert len(found) == 2, found
    return found


def _rules(css, selector):
    return " ".join(re.findall(re.escape(selector) + r"\s*\{([^}]*)\}", css))


def test_jupiter_frame_gets_earth_ring_at_true_scale(client):
    section = duel(client, left="jupiter", right="earth")
    jupiter, earth = frames(section)
    assert PORTRAIT.match(jupiter).groups() == ("jupiter", "100.0")
    assert jupiter.count("duel-earth-ring\"") == 1
    ring = float(RING.search(jupiter).group(1))
    assert ring == pytest.approx(8.9213, abs=0.001)
    assert 8.85 < ring < 8.95
    assert LABEL in jupiter
    # The ring follows the portrait as a sibling, never nested inside it.
    assert jupiter.index("duel-portrait") < jupiter.index("duel-earth-ring")
    assert "duel-earth-ring" not in earth


def test_ring_follows_the_larger_planet_to_the_right(client):
    left, right = frames(duel(client, left="earth", right="jupiter"))
    assert "duel-earth-ring" not in left
    assert float(RING.search(right).group(1)) == pytest.approx(8.9213, abs=0.001)


def test_no_ring_when_earth_would_overflow_the_frame(client):
    section = duel(client, left="mercury", right="mars")
    assert "duel-earth-ring" not in section
    assert "Earth, same scale" not in section


@pytest.mark.parametrize(("left", "right"), list(itertools.product(DIAMETERS, repeat=2)))
def test_ring_rule_for_every_pair(client, left, right):
    section = duel(client, left=left, right=right)
    largest = max(DIAMETERS[left], DIAMETERS[right])
    rings = RING.findall(section)
    if largest < EARTH:
        assert rings == [] and "duel-earth-ring" not in section
        return
    assert len(rings) == 1 and section.count(LABEL) == 1
    assert float(rings[0]) == pytest.approx(100 * EARTH / largest, abs=0.001)
    big_index = 0 if DIAMETERS[left] >= DIAMETERS[right] else 1
    assert RING.search(frames(section)[big_index])
    # Ring and label live only inside the aria-hidden frame, not in captions.
    for caption in re.findall(r"<figcaption>(.*?)</figcaption>", section, re.DOTALL):
        assert "Earth, same scale" not in caption


@pytest.mark.parametrize(("left", "right", "note", "sentence"), [
    ("jupiter", "earth", "Full circle = Jupiter, 142,984 km",
     "Jupiter is <strong>11.2</strong> times as wide as Earth."),
    ("mercury", "mars", "Full circle = Mars, 6,792 km",
     "Mars is <strong>1.39</strong> times as wide as Mercury."),
    ("saturn", "mercury", "Full circle = Saturn, 120,536 km",
     "Saturn is <strong>24.7</strong> times as wide as Mercury."),
    ("mercury", "saturn", "Full circle = Saturn, 120,536 km",
     "Saturn is <strong>24.7</strong> times as wide as Mercury."),
    ("earth", "earth", "Full circle = Earth, 12,756 km",
     "Both picks are Earth, so they are <strong>exactly the same size</strong>."),
])
def test_scale_note_names_reference_directly_under_ratio(client, left, right, note, sentence):
    section = duel(client, left=left, right=right)
    note_tag = f'<p class="duel-scale-note">{note}</p>'
    button, ratio = section.index(BUTTON), section.index(RATIO)
    note_at, portraits = section.index(note_tag), section.index(PORTRAITS)
    assert button < ratio < note_at < portraits
    assert section[button + len(BUTTON):ratio].strip() == "</form>"
    ratio_end = section.index("</p>", ratio) + len("</p>")
    assert section[ratio:ratio_end] == f"{RATIO}{sentence}</p>"
    assert section[ratio_end:note_at].strip() == ""
    assert section[note_at + len(note_tag):portraits].strip() == ""
    assert section.count('class="duel-ratio"') == 1
    assert section.count("duel-scale-note") == 1
    assert "for this pair only" not in section


@pytest.mark.parametrize(("left", "right"), list(itertools.product(DIAMETERS, repeat=2)))
def test_scale_note_names_larger_planet_for_every_pair(client, left, right):
    big = max((left, right), key=DIAMETERS.get)
    section = duel(client, left=left, right=right)
    assert f'<p class="duel-scale-note">Full circle = {NAMES[big]}, {DIAMETERS[big]:,} km</p>' in section


def test_error_path_has_no_note_or_ring(client):
    section = duel(client, left="pluto", right="earth")
    assert 'id="duel-error"' in section
    assert "duel-scale-note" not in section
    assert "duel-earth-ring" not in section


ZOOM_BLOCK = re.compile(r'\n *<a class="scale-zoom".*?</a>(?=\n)', re.DOTALL)
COUNT_BLOCK = re.compile(r'\n *\n *<div class="duel-count".*?</div>\n *(?=\n)', re.DOTALL)
RING_PAIR = re.compile(r'<span class="duel-earth-ring" style="--ring: [\d.]+%">' + re.escape(LABEL) + "</span>")
NOTE_NOW = re.compile(r'<p class="duel-scale-note">Full circle = [A-Z][a-z]+, [\d,]+ km</p>')
NOTE_BEFORE = ('<p class="duel-scale-note">Drawn to scale for this pair only: '
               "the larger planet always fills the same circle.</p>")


def test_scale_note_is_bordered_callout_at_body_size(client):
    css = client.get("/static/arcade.css").text
    note = _rules(css, ".duel-scale-note")
    assert re.search(r"(?<![-\w])border:\s*\d+px solid", note), note
    sizes = re.findall(r"font-size:\s*([\d.]+)rem", note)
    assert all(float(size) >= 1 for size in sizes), sizes
    assert "font-size" not in note or sizes, "font-size must be in rem"


def test_ring_css_is_dashed_circle_on_the_frame_baseline(client):
    css = client.get("/static/arcade.css").text
    assert "position: relative" in _rules(css, ".duel-frame")
    ring = _rules(css, ".duel-earth-ring")
    for decl in ("position: absolute", "bottom: 0", "aspect-ratio: 1", "border-radius: 50%", "dashed",
                 "width: var(--ring)"):
        assert decl in ring, (decl, ring)
    label = _rules(css, ".duel-earth-ring-label")
    assert "position: absolute" in label
    # Placed from the ring it sits in; a var() defined only on another element would void the declaration.
    assert "bottom: calc(100% + " in label and "var(--ring)" not in label, label
    size = re.findall(r"font-size:\s*([\d.]+)rem", label)
    assert size and float(size[-1]) >= 0.875, size


@pytest.mark.parametrize(("left", "right", "wide"), [
    ("jupiter", "earth", 1280), ("earth", "jupiter", 390), ("saturn", "earth", 1280), ("uranus", "venus", 390),
])
def test_ring_and_label_do_not_overlap_in_a_browser(client, left, right, wide):
    sync_api = pytest.importorskip("playwright.sync_api")

    def serve(route):
        response = client.get(route.request.url[len(BASE):])
        route.fulfill(status=response.status_code, body=response.content,
                      content_type=response.headers.get("content-type"))

    measure = """() => {
      const rect = (node) => node.getBoundingClientRect().toJSON();
      const portraits = [...document.querySelectorAll(".duel-portrait")].map(rect);
      const ring = document.querySelector(".duel-earth-ring");
      return {
        ring: rect(ring), label: rect(document.querySelector(".duel-earth-ring-label")),
        frame: rect(ring.parentElement), big: portraits.reduce((a, b) => (a.width >= b.width ? a : b)),
        style: getComputedStyle(ring).borderTopStyle, scroll: document.documentElement.scrollWidth,
      };
    }"""
    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": wide, "height": 900})
            page.route("**/*", serve)
            page.goto(f"{BASE}/?left={left}&right={right}")
            got = page.evaluate(measure)
        finally:
            browser.close()
    ring, label, big = got["ring"], got["label"], got["big"]
    earth_pct = 100 * EARTH / max(DIAMETERS[left], DIAMETERS[right])
    assert ring["width"] == pytest.approx(big["width"] * earth_pct / 100, abs=0.6), "ring is Earth at the frame's scale"
    assert ring["bottom"] == pytest.approx(big["bottom"], abs=0.6), "ring shares the portraits' baseline"
    assert ring["width"] > 4, "ring is visible"
    assert got["style"] == "dashed"
    assert label["bottom"] <= ring["top"], "label sits above the ring, not over it"
    assert label["left"] >= got["frame"]["left"] - 0.5 and label["right"] <= got["frame"]["right"] + 0.5
    assert got["scroll"] <= wide
