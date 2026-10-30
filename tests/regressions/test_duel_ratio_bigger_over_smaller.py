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


def selected(section, name):
    return re.findall(rf'<input type="radio" id="[\w-]+" name="{name}" value="(\w+)" checked>', section)


def test_smaller_first_names_the_bigger_planet_first(client):
    section = duel(client.get("/?left=mercury&right=neptune").text)
    assert sentence(section) == "Neptune is 10.2 times as wide as Mercury."
    assert "diameter is 0.1" not in section


def test_default_is_jupiter_versus_earth(client):
    section = duel(client.get("/?left=jupiter&right=earth").text)
    assert sentence(section) == "Jupiter is 11.2 times as wide as Earth."
    section = duel(client.get("/").text)
    assert selected(section, "left") == ["jupiter"] and selected(section, "right") == ["earth"]
    assert sentence(section) == "Jupiter is 11.2 times as wide as Earth."
    assert "142,984 km" in section and "12,756 km" in section
    assert len(re.findall(r'class="duel-portrait"', section)) == 2


def test_order_of_picks_does_not_change_the_sentence(client):
    forward = sentence(duel(client.get("/?left=jupiter&right=earth").text))
    reverse = sentence(duel(client.get("/?left=earth&right=jupiter").text))
    assert forward == reverse == "Jupiter is 11.2 times as wide as Earth."


@pytest.mark.parametrize("slug", list(DIAMETERS))
def test_same_planet_twice_says_exactly_the_same_size(client, slug):
    text = sentence(duel(client.get("/", params={"left": slug, "right": slug}).text))
    assert text == f"Both picks are {slug.title()}, so they are exactly the same size."
    assert "times" not in text
