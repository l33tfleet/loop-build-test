"""Issue #55: quiz circles stay the same neutral size until a guess, then appear at true scale."""
import re

import pytest

DIAMETERS = {"jupiter": 142984, "earth": 12756, "mercury": 4879, "mars": 6792, "neptune": 49528, "uranus": 51118}
PAIRS = [(1, "jupiter", "earth"), (2, "mercury", "mars"), (3, "neptune", "uranus")]
CIRCLE = re.compile(r'<span class="quiz-planet" data-planet="(\w+)" style="width: ([\d.]+)%"></span>')
TRACK = re.compile(r'<div class="quiz-scale" data-scale="(\w+)">(.*?)</div>', re.DOTALL)


def quiz(html):
    match = re.search(r'<section class="planet-quiz"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "Quiz panel missing"
    return match.group(1)


def track(url, client):
    panel = quiz(client.get(url).text)
    match = TRACK.search(panel)
    assert match, "scale track missing"
    return panel, match.group(1), [(slug, float(width)) for slug, width in CIRCLE.findall(match.group(2))]


@pytest.mark.parametrize("number,left,right", PAIRS)
def test_before_answering_circles_are_equal_and_neutral(client, number, left, right):
    panel, scale, circles = track(f"/?round={number}", client)
    assert scale == "neutral"
    assert [slug for slug, _ in circles] == [left, right]
    assert [width for _, width in circles] == [100, 100], "equal sizes so the circles don't give the answer away"
    assert "Drawn to scale" not in panel
    assert "until you answer" in panel


def test_home_page_before_answering_does_not_show_jupiter_bigger(client):
    _, scale, circles = track("/", client)
    assert scale == "neutral"
    assert dict(circles) == {"jupiter": 100, "earth": 100}


@pytest.mark.parametrize("number,left,right", PAIRS)
@pytest.mark.parametrize("side", ["left", "right"])
def test_after_answering_circles_appear_at_true_scale(client, number, left, right, side):
    choice = left if side == "left" else right
    panel, scale, circles = track(f"/?round={number}&choice={choice}", client)
    assert scale == "true"
    assert [slug for slug, _ in circles] == [left, right]
    largest = max(DIAMETERS[left], DIAMETERS[right])
    for slug, width in circles:
        assert width == pytest.approx(100 * DIAMETERS[slug] / largest, abs=0.01)
    assert "Drawn to scale" in panel
    assert "until you answer" not in panel


def test_after_answering_jupiter_is_eleven_earths_wide(client):
    _, _, circles = track("/?round=1&choice=earth", client)
    found = dict(circles)
    assert found["jupiter"] == 100
    assert 11.1 < found["jupiter"] / found["earth"] < 11.3


def test_neutral_circles_share_one_look_in_css(client):
    css = client.get("/static/arcade.css").text
    rule = re.search(r'\.quiz-scale\[data-scale="neutral"\] \.quiz-planet \{([^}]*)\}', css)
    assert rule, "neutral circle style missing"
    assert "background" in rule.group(1)
    assert "width" not in rule.group(1), "width still comes from the markup"
