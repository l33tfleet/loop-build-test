"""#88: URL-carried quiz scores give each three-round game an ending."""
import re
from html import unescape

import pytest


def quiz(response):
    assert response.status_code == 200
    match = re.search(r'<section class="planet-quiz"[^>]*>(.*?)</section>', response.text, re.DOTALL)
    assert match, "Quiz panel missing"
    return match.group(1)


def form(panel):
    match = re.search(r'<form\b[^>]*action="([^"]+)"[^>]*method="get"[^>]*>(.*?)</form>', panel, re.DOTALL)
    assert match
    fields = dict(re.findall(r'<input type="hidden" name="([^"]+)" value="([^"]*)">', match[2]))
    return unescape(match[1]), fields


def next_link(panel, label="Next"):
    match = re.search(rf'<a class="quiz-next" href="([^"]+)">{label}</a>', panel)
    assert match, f"Missing {label} link"
    return unescape(match[1])


@pytest.mark.parametrize("score", [None, "", "oops", "1.5", "-1", "4", "999", "9" * 5000])
def test_invalid_or_missing_scores_fall_back_to_zero(client, score):
    params = {"round": "3"}
    if score is not None:
        params["score"] = score
    panel = quiz(client.get("/", params=params))
    assert form(panel)[1]["score"] == "0"
    assert "You got" not in panel and "Play again" not in panel
    for choice, total in (("uranus", 1), ("neptune", 0)):
        answered = quiz(client.get("/", params={**params, "choice": choice}))
        assert f"You got {total} of 3!" in answered
        assert form(answered)[1]["score"] == "0"


@pytest.mark.parametrize("score", range(4))
@pytest.mark.parametrize("choice", ["uranus", "neptune"])
def test_valid_scores_are_preserved_and_result_is_capped(client, score, choice):
    params = {"round": "3", "score": str(score), "choice": choice}
    panel = quiz(client.get("/", params=params))
    assert form(panel)[1]["score"] == str(score)
    assert f"You got {min(3, score + (choice == 'uranus'))} of 3!" in panel
    assert quiz(client.get("/", params=params)) == panel


@pytest.mark.parametrize("score", ["oops", "-1", "4"])
def test_normalized_score_carries_through_next(client, score):
    panel = quiz(client.get("/", params={"round": "1", "choice": "jupiter", "score": score}))
    assert form(panel)[1]["score"] == "0"
    following = quiz(client.get(next_link(panel)))
    assert form(following)[1] == {"round": "2", "score": "1"}


def test_revisiting_answer_uses_incoming_score_without_accumulating(client):
    params = {"round": "3", "score": "2", "choice": "uranus"}
    answered = quiz(client.get("/", params=params))
    assert "You got 3 of 3!" in answered
    action, fields = form(answered)
    revised = quiz(client.get(action, params={**fields, "choice": "neptune"}))
    assert "You got 2 of 3!" in revised
    assert form(revised)[1]["score"] == "2"


def test_invalid_third_round_answer_does_not_complete_game(client):
    response = client.get("/?round=3&choice=pluto&score=2")
    assert response.status_code == 422
    assert "Choose one of the two planets in this round." in response.text
    assert "You got" not in response.text
    assert "Play again" not in response.text


@pytest.mark.parametrize("score", ["00", "01", "+1", " 1", "1 ", "１", "١", "3.0"])
def test_only_canonical_score_strings_are_accepted(client, score):
    panel = quiz(client.get("/", params={"round": "1", "choice": "jupiter", "score": score}))
    assert form(panel)[1]["score"] == "0"
    assert next_link(panel) == "/?round=2&score=1"
