"""#100: deterministic quiz sets rotate on replay and travel in the URL."""
import importlib
import json
import re
from html import unescape
from pathlib import Path
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
            assert next_link(panel, "Play again") == "/?round=1&set=1"
            reset = quiz(client.get(next_link(panel, "Play again")))
            assert form(reset)[1] == {"round": "1", "score": "0", "set": "1"}
            assert "You got" not in reset and "Correct" not in reset


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
        assert link == "/?round=1&set=1"
    next_panel = quiz(client.get(link))
    assert f"Round {number % 3 + 1} of 3" in next_panel
    assert "Correct" not in next_panel and "Not quite" not in next_panel
    assert all("disabled" not in attrs for attrs in re.findall(r'<button\b([^>]*)>', next_panel))



def choices(panel):
    return re.findall(r'<button type="submit" name="choice" value="(\w+)">', panel)


def test_play_again_rotates_pairs_and_wraps_with_url_only_state(client):
    module = importlib.import_module("app.sections.20_planet_quiz")
    planets = json.loads(Path("data/planets.json").read_text())["planets"]
    diameters = {p["name"].lower(): p["diameter_km"] for p in planets}
    panel = quiz(client.get("/?round=1"))
    original_pair = choices(panel)
    assert original_pair == ["jupiter", "earth"]
    starts = []
    for set_number in range(len(module.QUIZ_SETS) + 1):
        first_pair = choices(panel)
        if starts:
            assert first_pair != starts[-1]
        starts.append(first_pair)
        pairs = module.QUIZ_SETS[set_number % len(module.QUIZ_SETS)]
        for number, expected_pair in enumerate(pairs, 1):
            assert f"Round {number} of {len(pairs)}" in panel
            pair = choices(panel)
            assert pair == list(expected_pair)
            assert len(set(pair)) == 2 and set(pair) <= diameters.keys()
            action, fields = form(panel)
            if set_number:
                assert fields["set"] == str(set_number % len(module.QUIZ_SETS))
            winner = max(pair, key=diameters.get)
            params = {**fields, "choice": winner}
            response = client.get(action, params=params)
            assert "set-cookie" not in response.headers
            answered = quiz(response)
            assert form(answered)[1] == fields
            assert quiz(client.get(action, params=params)) == answered
            if number < len(pairs):
                link = next_link(answered)
                if set_number:
                    assert parse_qs(urlsplit(link).query)["set"] == fields["set"].split()
            else:
                assert f"You got {len(pairs)} of {len(pairs)}!" in answered
                link = next_link(answered, "Play again")
                assert parse_qs(urlsplit(link).query) == {
                    "round": ["1"], "set": [str((set_number + 1) % len(module.QUIZ_SETS))],
                }
            panel = quiz(client.get(link))
            assert quiz(client.get(link)) == panel
        assert form(panel)[1]["score"] == "0"
        assert "Correct" not in panel and "You got" not in panel
    assert starts[-1] == original_pair


@pytest.mark.parametrize("value", ["", "-1", "999", "01", "+1", " 1", "1.0", "１", "oops", "<script>"])
def test_invalid_set_uses_quiz_error_and_restart(client, value):
    response = client.get("/", params={"set": value, "round": "1", "choice": "jupiter"})
    assert response.status_code == 422
    assert 'role="alert"' in response.text
    assert 'href="/?round=1">Start at round 1</a>' in response.text
    assert "You got" not in response.text and "<script>" not in response.text
    assert choices(quiz(client.get("/?round=1"))) == ["jupiter", "earth"]


def test_selected_set_length_controls_bounds_and_score(client, monkeypatch):
    module = importlib.import_module("app.sections.20_planet_quiz")
    monkeypatch.setattr(module, "QUIZ_SETS", (module.QUIZ_PAIRS, (("venus", "earth"),)))
    panel = quiz(client.get("/?round=1&set=1&score=1&choice=earth"))
    assert "Round 1 of 1" in panel
    assert "You got 1 of 1!" in panel
    assert next_link(panel, "Play again") == "/?round=1&set=0"
    response = client.get("/?round=2&set=1")
    assert response.status_code == 422
    assert "Choose a round from 1 through 1." in response.text
