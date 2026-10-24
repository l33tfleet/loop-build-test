"""Issue #43: the quiz's planet drawings are sized in proportion to each planet's real diameter."""
import re

import pytest

DIAMETERS = {"jupiter": 142984, "earth": 12756, "mercury": 4879, "mars": 6792, "neptune": 49528, "uranus": 51118}
PAIRS = [(1, "jupiter", "earth"), (2, "mercury", "mars"), (3, "neptune", "uranus")]


def quiz(html):
    match = re.search(r'<section class="planet-quiz"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "Quiz panel missing"
    return match.group(1)


def drawings(panel):
    return re.findall(r'<span class="quiz-planet" data-planet="(\w+)" style="width: ([\d.]+)%"></span>', panel)


@pytest.mark.parametrize("number,left,right", PAIRS)
def test_answer_draws_both_planets_to_relative_scale(client, number, left, right):
    panel = quiz(client.get(f"/?round={number}&choice={left}").text)
    found = drawings(panel)
    assert [slug for slug, _ in found] == [left, right]
    widths = {slug: float(width) for slug, width in found}
    largest = max(DIAMETERS[left], DIAMETERS[right])
    for slug in (left, right):
        assert widths[slug] == pytest.approx(100 * DIAMETERS[slug] / largest, abs=0.01)
    assert widths[left] / widths[right] == pytest.approx(DIAMETERS[left] / DIAMETERS[right], rel=1e-3)


def test_jupiter_is_about_eleven_earths_wide(client):
    widths = dict(drawings(quiz(client.get("/?round=1&choice=earth").text)))
    assert float(widths["jupiter"]) == 100
    assert 11 < float(widths["jupiter"]) / float(widths["earth"]) < 11.4


def test_drawings_sit_at_the_bottom_of_the_answer_with_labels(client):
    panel = quiz(client.get("/?round=1&choice=jupiter").text)
    figure = re.search(r'<div class="quiz-scale"[^>]*>(.*?)</div>', panel, re.DOTALL)
    assert figure, "scale drawing missing"
    assert panel.index('class="quiz-scale"') > panel.index("has the larger diameter.")
    assert panel.index('class="quiz-scale"') < panel.index('class="quiz-next"')
    assert "Jupiter" in figure.group(1) and "Earth" in figure.group(1)
    assert "to scale" in panel


@pytest.mark.parametrize("number", [1, 2, 3])
def test_unanswered_round_does_not_give_the_answer_away(client, number):
    panel = quiz(client.get(f"/?round={number}").text)
    assert drawings(panel) == []


def test_css_keeps_drawings_round_and_unscaled_by_fixed_widths(client):
    css = client.get("/static/arcade.css").text
    rule = re.search(r"\.quiz-planet \{([^}]*)\}", css)
    assert rule, ".quiz-planet rule missing"
    assert "aspect-ratio: 1" in rule.group(1)
    assert "border-radius: 50%" in rule.group(1)
    assert not re.search(r"(?<![-\w])width:", rule.group(1)), "width comes from the diameter, not CSS"
    # A floor on the smaller planet would break the ratio.
    assert "min-width" not in rule.group(1)
