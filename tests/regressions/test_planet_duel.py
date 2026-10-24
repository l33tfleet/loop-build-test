import re

import pytest

DIAMETERS = {
    "mercury": 4879, "venus": 12104, "earth": 12756, "mars": 6792,
    "jupiter": 142984, "saturn": 120536, "uranus": 51118, "neptune": 49528,
}


def duel(html):
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


def sentence(section):
    match = re.search(r'<p class="duel-ratio"[^>]*>(.*?)</p>', section, re.DOTALL)
    return " ".join(re.sub(r"<[^>]+>", "", match.group(1)).split()) if match else None


def radios(section, name):
    return re.findall(rf'<input type="radio" id="([\w-]+)" name="{name}" value="(\w+)"( checked)?>', section)


def selected(section, name):
    return [value for _, value, checked in radios(section, name) if checked]


def test_duel_is_first_panel_with_labeled_selectors_and_get_form(client):
    html = client.get("/").text
    main = html.split("<main>", 1)[1]
    assert main.lstrip().startswith('<section class="planet-duel"')
    section = duel(html)
    assert re.search(r'<form\b[^>]*action="/"[^>]*method="get"', section)
    groups = re.findall(r'<fieldset\b[^>]*>\s*<legend>([^<]+)</legend>(.*?)</fieldset>', section, re.DOTALL)
    assert [legend for legend, _ in groups] == ["First planet", "Second planet"]
    for (_, group), name in zip(groups, ("left", "right")):
        found = radios(group, name)
        assert [value for _, value, _ in found] == list(DIAMETERS)
        for radio_id, value, _ in found:
            assert f'<label for="{radio_id}">{value.title()}</label>' in group
    assert re.search(r'<button type="submit"', section)
    assert "tabindex" not in section


def test_default_is_jupiter_versus_earth(client):
    section = duel(client.get("/").text)
    assert selected(section, "left") == ["jupiter"]
    assert selected(section, "right") == ["earth"]
    assert sentence(section) == "Jupiter's diameter is 11.2 times Earth's."
    assert "142,984 km" in section and "12,756 km" in section
    assert len(re.findall(r'class="duel-portrait"', section)) == 2


@pytest.mark.parametrize(("left", "right"), [
    ("jupiter", "earth"), ("earth", "jupiter"), ("mercury", "mars"), ("neptune", "uranus"), ("venus", "saturn"),
])
def test_ratio_is_left_over_right_to_one_decimal(client, left, right):
    response = client.get("/", params={"left": left, "right": right})
    assert response.status_code == 200
    section = duel(response.text)
    ratio = f"{DIAMETERS[left] / DIAMETERS[right]:.1f}"
    assert sentence(section) == f"{left.title()}'s diameter is {ratio} times {right.title()}'s."
    assert selected(section, "left") == [left] and selected(section, "right") == [right]
    assert f"{DIAMETERS[left]:,} km" in section and f"{DIAMETERS[right]:,} km" in section


PORTRAIT = re.compile(r'<span class="duel-portrait" data-planet="(\w+)" style="width: ([\d.]+)%"></span>')


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


def test_ratio_direction_flips(client):
    forward = sentence(duel(client.get("/?left=jupiter&right=earth").text))
    reverse = sentence(duel(client.get("/?left=earth&right=jupiter").text))
    assert "11.2" in forward and "0.1" in reverse


@pytest.mark.parametrize("slug", ["earth", "mars", "neptune"])
def test_identical_planets_show_one(client, slug):
    section = duel(client.get("/", params={"left": slug, "right": slug}).text)
    assert sentence(section) == f"{slug.title()}'s diameter is 1.0 times {slug.title()}'s."


@pytest.mark.parametrize("params", [
    {"left": "pluto"}, {"right": "sun"}, {"left": "", "right": "earth"}, {"left": "Jupiter"},
    {"left": "<script>alert(1)</script>", "right": "earth"},
])
def test_unknown_slug_returns_clear_validation_response(client, params):
    response = client.get("/", params=params)
    assert response.status_code == 422
    section = duel(response.text)
    assert 'role="alert"' in section
    assert "Choose two planets from the lists" in section
    assert sentence(section) is None
    assert "<script>" not in response.text
    assert 'data-marker="solar-arcade"' in response.text


def test_healthz_and_convert_still_work(client):
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/convert", params={"value": 1, "src": "km", "dst": "mi"}).status_code == 200
