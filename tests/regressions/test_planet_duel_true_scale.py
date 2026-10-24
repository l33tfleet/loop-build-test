import re

import pytest

DIAMETERS = {
    "mercury": 4879, "venus": 12104, "earth": 12756, "mars": 6792,
    "jupiter": 142984, "saturn": 120536, "uranus": 51118, "neptune": 49528,
}

PORTRAIT = re.compile(r'<span class="duel-portrait" data-planet="(\w+)" style="width: ([\d.]+)%"></span>')


def duel(html):
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


def portrait_widths(client, left, right):
    section = duel(client.get("/", params={"left": left, "right": right}).text)
    return [(slug, float(width)) for slug, width in PORTRAIT.findall(section)]


def test_default_portraits_are_drawn_to_true_scale(client):
    found = portrait_widths(client, "jupiter", "earth")
    assert [slug for slug, _ in found] == ["jupiter", "earth"]
    (_, jupiter), (_, earth) = found
    assert jupiter == 100
    assert earth == pytest.approx(100 * 12756 / 142984, abs=0.01)
    assert 11.1 < jupiter / earth < 11.3


@pytest.mark.parametrize(("left", "right"), [
    ("earth", "jupiter"), ("mercury", "mars"), ("neptune", "uranus"), ("venus", "saturn"), ("mercury", "jupiter"),
])
def test_portrait_width_is_diameter_over_larger_on_one_linear_scale(client, left, right):
    found = portrait_widths(client, left, right)
    assert [slug for slug, _ in found] == [left, right]
    largest = max(DIAMETERS[left], DIAMETERS[right])
    for slug, width in found:
        assert width == pytest.approx(100 * DIAMETERS[slug] / largest, abs=0.01)


@pytest.mark.parametrize("slug", ["earth", "jupiter", "mercury"])
def test_identical_picks_draw_two_equal_circles(client, slug):
    assert portrait_widths(client, slug, slug) == [(slug, 100.0), (slug, 100.0)]


def test_portrait_css_has_equal_columns_shared_baseline_and_no_floor(client):
    css = client.get("/static/arcade.css").text
    assert "grid-template-columns: 1fr 1fr" in re.search(r"\.duel-portraits \{([^}]*)\}", css).group(1)
    assert "align-items: flex-end" in re.search(r"\.duel-frame \{([^}]*)\}", css).group(1)
    portrait = re.search(r"\.duel-portrait \{([^}]*)\}", css).group(1)
    assert "aspect-ratio: 1" in portrait and "border-radius: 50%" in portrait
    assert not re.search(r"(?<![-\w])width:", portrait), "width comes from the diameter, not CSS"
    for body in re.findall(r"\.duel-[\w-]+[^{]*\{([^}]*)\}", css):
        assert "min-width" not in body and "min-height" not in body
        assert "clamp(" not in body and "log(" not in body
