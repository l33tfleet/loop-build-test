"""#128: a perfect quiz gets a decorative ring of stars around the banner; it bursts once, or sits still."""
import re

import pytest

PERFECT = "/?round=3&score=2&choice=uranus"
STARS = re.compile(r'<span class="quiz-stars" aria-hidden="true">((?:\s*<span class="quiz-star"></span>)+)\s*</span>')


def quiz(response):
    assert response.status_code == 200
    match = re.search(r'<section class="planet-quiz"[^>]*>(.*?)</section>', response.text, re.DOTALL)
    assert match, "Quiz panel missing"
    return match.group(1)


def status(panel):
    match = re.search(r'<div class="quiz-answer" role="status">(.*?)</div>', panel, re.DOTALL)
    assert match, "Status region missing"
    return match.group(1)


def visible_text(html):
    return " ".join(re.sub(r"<[^>]+>", " ", html).split())


def media_body(css, condition):
    start = css.find(f"@media ({condition})")
    assert start != -1, f"Missing @media ({condition})"
    depth = 0
    for index in range(css.index("{", start), len(css)):
        depth += {"{": 1, "}": -1}.get(css[index], 0)
        if depth == 0:
            return css[start:index]
    raise AssertionError("Unclosed media query")


def test_perfect_score_has_a_ring_of_stars_right_before_the_banner(client):
    region = status(quiz(client.get(PERFECT)))
    match = STARS.search(region)
    assert match, "Star ring missing"
    assert match.group(1).count('class="quiz-star"') >= 6
    after = region[match.end():].lstrip()
    assert after.startswith('<p class="quiz-perfect"><strong>Perfect score!</strong> You got 3 of 3!</p>')


def test_stars_add_no_text_to_the_status_region(client):
    region = status(quiz(client.get(PERFECT)))
    assert "★" not in region
    without = STARS.sub("", region)
    assert visible_text(region) == visible_text(without)
    assert visible_text(region).endswith("Perfect score! You got 3 of 3! Hand the phone over: can they beat it?")


def test_star_glyph_is_drawn_in_local_css_with_empty_alt_text(client):
    css = client.get("/static/arcade.css").text
    rule = re.search(r'\.quiz-star::before \{([^}]*)\}', css)
    assert rule, "Star glyph rule missing"
    assert re.search(r'content: "★" / ""', rule[1])
    assert "url(" not in css and "@import" not in css and "@font-face" not in css


def test_stars_burst_once_and_only_without_a_reduced_motion_preference(client):
    css = client.get("/static/arcade.css").text
    motion = media_body(css, "prefers-reduced-motion: no-preference")
    assert re.search(r"\.quiz-star \{[^}]*animation: quiz-star-burst [^;}]*\b1\b", motion)
    assert "@keyframes quiz-star-burst" in motion
    assert "infinite" not in motion
    outside = css.replace(motion, "")
    assert not re.search(r"\banimation\b|@keyframes|\btransition\b", outside), "Motion must stay inside the media query"
    # Without the burst the stars still show where they end up.
    still = re.search(r"\.quiz-star \{([^}]*)\}", outside)
    assert still and "opacity: 0" not in still[1] and "display: none" not in still[1]


@pytest.mark.parametrize("url", [
    "/?round=3&score=0&choice=uranus",
    "/?round=3&score=1&choice=uranus",
    "/?round=3&score=3&choice=neptune",
    "/?round=2&score=1&choice=mars",
    "/?round=3&score=2",
])
def test_anything_but_a_perfect_finish_has_no_stars(client, url):
    assert "quiz-star" not in quiz(client.get(url))


def test_smoke_routes_still_work(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/convert?value=1&src=km&dst=mi").status_code == 200
