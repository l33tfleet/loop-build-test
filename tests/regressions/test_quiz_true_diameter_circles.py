"""Issue #46: quiz circle sizes come straight from true diameters, so Jupiter is ~11 Earths wide."""
import re

import pytest

DIAMETERS = {"jupiter": 142984, "earth": 12756, "mercury": 4879, "mars": 6792, "neptune": 49528, "uranus": 51118}
PAIRS = [(1, "jupiter", "earth"), (2, "mercury", "mars"), (3, "neptune", "uranus")]
CIRCLE = re.compile(r'<span class="quiz-planet" data-planet="(\w+)" style="width: ([\d.]+)%"></span>')


def quiz(html):
    match = re.search(r'<section class="planet-quiz"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "Quiz panel missing"
    return match.group(1)


def widths(url, client):
    return {slug: float(width) for slug, width in CIRCLE.findall(quiz(client.get(url).text))}


def test_both_circles_share_one_track_so_percentages_compare(client):
    panel = quiz(client.get("/").text)
    track = re.search(r'<div class="quiz-scale"[^>]*>(.*?)</div>', panel, re.DOTALL)
    assert track, "scale track missing"
    assert len(CIRCLE.findall(track.group(1))) == 2


def test_css_does_not_floor_or_compress_circle_sizes(client):
    css = client.get("/static/arcade.css").text
    rules = re.findall(r"\.quiz-[\w-]+[^{]*\{([^}]*)\}", css)
    assert rules, "quiz scale CSS missing"
    planet = re.search(r"\.quiz-planet \{([^}]*)\}", css)
    assert planet and "aspect-ratio: 1" in planet.group(1) and "border-radius: 50%" in planet.group(1)
    assert not re.search(r"(?<![-\w])width:", planet.group(1)), "width comes from the diameter, not CSS"
    for body in rules:
        assert "min-width" not in body and "min-height" not in body
        assert "clamp(" not in body and "log(" not in body
