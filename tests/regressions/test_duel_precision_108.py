"""Duel precision follows the unrounded larger/smaller ratio (#108)."""

import importlib
import re

import pytest

context = importlib.import_module("app.sections.10_planet_duel").context
DIAMETERS = {
    "mercury": 4879, "venus": 12104, "earth": 12756, "mars": 6792,
    "jupiter": 142984, "saturn": 120536, "uranus": 51118, "neptune": 49528,
}


def duel_sentence(client, left, right):
    response = client.get("/", params={"left": left, "right": right})
    assert response.status_code == 200
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>',
                      response.text, re.DOTALL)
    assert match, "duel panel missing"
    section = match.group(1)
    for side, slug in (("left", left), ("right", right)):
        assert re.findall(
            rf'<input type="radio" id="[\w-]+" name="{side}" value="(\w+)" checked>',
            section,
        ) == [slug]
        assert f"{DIAMETERS[slug]:,} km" in section
    match = re.search(r'<p class="duel-ratio"[^>]*>(.*?)</p>', section, re.DOTALL)
    assert match, "duel sentence missing"
    return " ".join(re.sub(r"<[^>]+>", "", match.group(1)).split())


@pytest.mark.parametrize("left", list(DIAMETERS))
@pytest.mark.parametrize("right", list(DIAMETERS))
def test_all_selection_pairs_preserve_larger_first_contract(client, left, right):
    sentence = duel_sentence(client, left, right)
    if left == right:
        assert sentence == f"Both picks are {left.title()}, so they are exactly the same size."
        planets = [{"name": left.title(), "diameter_km": DIAMETERS[left]}]
        assert context({"planets": planets, "left": left, "right": right})["duel"]["ratio"] == "1.00"
        return
    big, small = sorted((left, right), key=DIAMETERS.get, reverse=True)
    ratio = DIAMETERS[big] / DIAMETERS[small]
    formatted = format(ratio, ".2f" if ratio < 2 else ".1f")
    assert float(formatted) >= 1
    assert sentence == f"{big.title()} is {formatted} times as wide as {small.title()}."


@pytest.mark.parametrize("left,right,expected", [
    ("uranus", "neptune", "Uranus is 1.03 times as wide as Neptune."),
    ("earth", "mars", "Earth is 1.88 times as wide as Mars."),
    ("jupiter", "earth", "Jupiter is 11.2 times as wide as Earth."),
])
@pytest.mark.parametrize("reverse", [False, True])
def test_requested_sentences_in_both_orders(client, left, right, expected, reverse):
    if reverse:
        left, right = right, left
    assert duel_sentence(client, left, right) == expected


@pytest.mark.parametrize("diameter,expected", [(1999, "2.00"), (2000, "2.0"), (2001, "2.0")])
@pytest.mark.parametrize("reverse", [False, True])
def test_precision_threshold_uses_unrounded_ratio(diameter, expected, reverse):
    planets = [{"name": "Earth", "diameter_km": diameter},
               {"name": "Mars", "diameter_km": 1000}]
    left, right = ("mars", "earth") if reverse else ("earth", "mars")
    duel = context({"planets": planets, "left": left, "right": right})["duel"]
    assert (duel["big"], duel["small"], duel["ratio"]) == ("Earth", "Mars", expected)
