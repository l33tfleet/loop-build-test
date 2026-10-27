"""#88: URL-carried quiz scores give each three-round game an ending."""
import re
from html import unescape
from urllib.parse import parse_qs, urlsplit

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


@pytest.mark.parametrize("choices,total", [(("jupiter", "mars", "uranus"), 3),
                                           (("earth", "mars", "uranus"), 2)])
def test_game_follows_forms_and_links_to_final_score(client, choices, total):
    panel = quiz(client.get("/?round=1"))
    score = 0
    for number, choice in enumerate(choices, 1):
        action, fields = form(panel)
        assert fields == {"round": str(number), "score": str(score)}
        assert re.search(rf'<button type="submit" name="choice" value="{choice}">', panel)
        assert "You got" not in panel
        params = {**fields, "choice": choice}
        panel = quiz(client.get(action, params=params))
        assert form(panel)[1] == fields  # Resubmitting keeps the pre-answer score.
        assert quiz(client.get(action, params=params)) == panel
        score += choice in ("jupiter", "mars", "uranus")
        if number < 3:
            link = next_link(panel)
            assert parse_qs(urlsplit(link).query) == {"round": [str(number + 1)], "score": [str(score)]}
            assert "You got" not in panel and "Play again" not in panel
            panel = quiz(client.get(link))
        else:
            status = re.search(r'<div class="quiz-answer" role="status">(.*?)</div>', panel, re.DOTALL)
            assert status and f"You got {total} of 3!" in status[1]
            assert ">Next</a>" not in panel
            assert next_link(panel, "Play again") == "/?round=1"
            reset = quiz(client.get(next_link(panel, "Play again")))
            assert form(reset)[1] == {"round": "1", "score": "0"}
            assert "You got" not in reset and "Correct" not in reset


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


@pytest.mark.parametrize("number,left,left_km,right,right_km,winner", [
    (1, "jupiter", 142984, "earth", 12756, "jupiter"),
    (2, "mercury", 4879, "mars", 6792, "mars"),
    (3, "neptune", 49528, "uranus", 51118, "uranus"),
])
@pytest.mark.parametrize("side", ["left", "right"])
def test_each_answer_reveals_values_and_advances_or_restarts(
    client, number, left, left_km, right, right_km, winner, side,
):
    choice = left if side == "left" else right
    url = f"/?round={number}&choice={choice}"
    panel = quiz(client.get(url))
    heading = re.search(r'<div class="quiz-answer" role="status">\s*<p><strong>([^<]+)</strong>', panel)
    assert heading and heading[1] == ("Correct" if choice == winner else "Not quite")
    assert "Try the next pair" not in panel
    assert ("Not quite" if choice == winner else "Correct") not in panel
    assert f"{left.title()}: {left_km:,} km" in panel
    assert f"{right.title()}: {right_km:,} km" in panel
    assert f"{winner.title()} has the larger diameter." in panel
    assert f"You chose {choice.title()}." in panel
    assert quiz(client.get(url)) == panel
    buttons = re.findall(r'<button\b([^>]*)>(.*?)</button>', panel, re.DOTALL)
    assert len(buttons) == 2
    for attrs, body in buttons:
        assert re.search(r"\bdisabled\b", attrs)
        assert ("Your pick" in body) == (f'value="{choice}"' in attrs)
    if number < 3:
        link = next_link(panel)
        assert link == f"/?round={number + 1}&score={int(choice == winner)}"
    else:
        link = next_link(panel, "Play again")
        assert link == "/?round=1"
    next_panel = quiz(client.get(link))
    assert f"Round {number % 3 + 1} of 3" in next_panel
    assert "Correct" not in next_panel and "Not quite" not in next_panel
    assert all("disabled" not in attrs for attrs in re.findall(r'<button\b([^>]*)>', next_panel))


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
