"""#114: a perfect quiz gets a banner and one optional bounce; the text carries the meaning."""
import re

import pytest

PERFECT = "/?round=3&score=2&choice=uranus"


def quiz(response):
    assert response.status_code == 200
    match = re.search(r'<section class="planet-quiz"[^>]*>(.*?)</section>', response.text, re.DOTALL)
    assert match, "Quiz panel missing"
    return match.group(1)


def status(panel):
    match = re.search(r'<div class="quiz-answer" role="status">(.*?)</div>', panel, re.DOTALL)
    assert match, "Status region missing"
    return match.group(1)


def sides(panel):
    return dict(re.findall(r'<span class="([^"]+)"><span class="quiz-frame"[^>]*><span class="quiz-planet" data-planet="(\w+)"',
                           panel))


def media_body(css, condition):
    start = css.find(f"@media ({condition})")
    assert start != -1, f"Missing @media ({condition})"
    depth = 0
    for index in range(css.index("{", start), len(css)):
        depth += {"{": 1, "}": -1}.get(css[index], 0)
        if depth == 0:
            return css[start:index]
    raise AssertionError("Unclosed media query")


def test_perfect_score_banner_is_inside_the_status_region(client):
    region = status(quiz(client.get(PERFECT)))
    assert '<p class="quiz-perfect"><strong>Perfect score!</strong> You got 3 of 3!</p>' in region
    assert '<p class="quiz-handover">Hand the phone over: can they beat it?</p>' in region


def test_perfect_score_keeps_the_play_again_link(client):
    assert ">Play again</a>" in quiz(client.get(PERFECT))


def test_any_set_gets_the_banner_when_every_answer_is_right(client):
    assert "Perfect score!" in status(quiz(client.get("/?round=3&score=2&set=1&choice=earth")))


@pytest.mark.parametrize("url,score", [
    ("/?round=3&score=1&choice=uranus", 2),
    ("/?round=3&score=0&choice=uranus", 1),
    ("/?round=3&score=2&choice=neptune", 2),
    ("/?round=3&score=0&choice=neptune", 0),
])
def test_score_below_three_keeps_the_plain_text(client, url, score):
    panel = quiz(client.get(url))
    assert f"<p>You got {score} of 3!</p>" in status(panel)
    assert "Perfect score!" not in panel and "Hand the phone over" not in panel
    assert "quiz-side-perfect" not in panel


def test_a_wrong_last_answer_never_celebrates(client):
    panel = quiz(client.get("/?round=3&score=3&choice=neptune"))
    assert "Not quite" in status(panel)
    assert "Perfect score!" not in panel and "quiz-side-perfect" not in panel


@pytest.mark.parametrize("url", ["/?round=2&score=1&choice=mars", "/?round=3&score=2", "/?round=1&score=3&choice=jupiter"])
def test_unfinished_rounds_do_not_celebrate(client, url):
    panel = quiz(client.get(url))
    assert "Perfect score!" not in panel and "quiz-side-perfect" not in panel


def test_only_the_winning_side_is_marked_to_bounce(client):
    assert sides(quiz(client.get(PERFECT))) == {"quiz-side": "neptune", "quiz-side quiz-side-perfect": "uranus"}


def test_bounce_runs_once_and_only_without_a_reduced_motion_preference(client):
    css = client.get("/static/arcade.css").text
    motion = media_body(css, "prefers-reduced-motion: no-preference")
    assert re.search(r"\.quiz-side-perfect \{[^}]*animation: quiz-bounce [^;}]*\b1\b", motion)
    assert "@keyframes quiz-bounce" in motion
    outside = css.replace(motion, "")
    assert not re.search(r"\banimation\b|@keyframes", outside), "Motion must stay inside the media query"
    assert "infinite" not in motion


def test_banner_is_readable_without_external_assets(client):
    css = client.get("/static/arcade.css").text
    rule = re.search(r"\.quiz-perfect \{([^}]*)\}", css)
    assert rule, "Banner rule missing"
    size = re.search(r"font-size: ([\d.]+)rem", rule[1])
    assert size and float(size[1]) * 16 >= 14
    assert "color: var(--paper)" in rule[1]  # #f4e9d2 on the navy status box is about 15:1.
    assert "url(" not in css
