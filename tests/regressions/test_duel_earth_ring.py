"""#122: a faint dashed Earth ring at the same scale, and a boxed 'Full circle = ...' callout."""
import itertools
import re
from hashlib import sha256

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
RING = re.compile(r'<span class="duel-earth-ring" style="--ring: ([\d.]+)%"></span>')
LABEL = '<span class="duel-earth-ring-label">Earth, same scale</span>'


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
RING_PAIR = re.compile(r'<span class="duel-earth-ring" style="--ring: [\d.]+%"></span>' + re.escape(LABEL))
NOTE_NOW = re.compile(r'<p class="duel-scale-note">Full circle = [A-Z][a-z]+, [\d,]+ km</p>')
NOTE_BEFORE = ('<p class="duel-scale-note">Drawn to scale for this pair only: '
               "the larger planet always fills the same circle.</p>")


# Supersedes test_zoom_box_links_inset.py::test_page_is_unchanged_apart_from_the_row_and_zoom_box: same pages
# and digests, so everything except the row, zoom link, Earth ring and reworded note stays byte-for-byte.
@pytest.mark.parametrize(("url", "status", "zooms", "blocks", "rings", "digest"), [
    ("/", 200, 1, 1, 1, "8a3828c60cf98b247ef920341a0b49347a756f13e6284047320accb8eefc2d4f"),
    ("/?left=mars&right=neptune", 200, 1, 1, 1, "b40575cda9a95d103dbe420300255d1a58c2367d0cb84c1d1e21ffa20687982b"),
    ("/?left=mars&right=earth", 200, 1, 1, 1, "d2d635e5603c175605df376f27a26f04f69236a513ad6b7c19430ca2399e29ec"),
    ("/?round=1&choice=earth", 200, 1, 1, 1, "0848700c8eef150b43c93e2163d873ba84caba8f011bd05baf2ffbcaacad2465"),
    ("/?left=pluto", 422, 1, 0, 0, "66553c68e4b191a5e080fedb98374bc297b1e9c80fff6d6b2da929f4a7a8adb5"),
])
def test_page_is_unchanged_apart_from_row_zoom_ring_and_note(client, url, status, zooms, blocks, rings, digest):
    response = client.get(url)
    assert response.status_code == status
    rest, found_zoom = ZOOM_BLOCK.subn("", response.text)
    assert found_zoom == zooms
    rest, found = COUNT_BLOCK.subn("", rest)
    assert found == blocks
    rest, found_rings = RING_PAIR.subn("", rest)
    assert found_rings == rings
    rest, found_notes = NOTE_NOW.subn(NOTE_BEFORE, rest)
    assert found_notes == (1 if status == 200 else 0)
    assert sha256(rest.encode()).hexdigest() == digest


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
    size = re.findall(r"font-size:\s*([\d.]+)rem", label)
    assert size and float(size[-1]) >= 0.875, size
