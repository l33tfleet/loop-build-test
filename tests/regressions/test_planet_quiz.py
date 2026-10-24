import re

import pytest

PAIRS = [
    (1, "jupiter", 142984, "earth", 12756, "jupiter"),
    (2, "mercury", 4879, "mars", 6792, "mars"),
    (3, "neptune", 49528, "uranus", 51118, "uranus"),
]


def quiz(response):
    match = re.search(r'<section class="planet-quiz"[^>]*>(.*?)</section>', response.text, re.DOTALL)
    assert match, "Quiz panel missing"
    return match.group(1)


@pytest.mark.parametrize("number,left,left_km,right,right_km,winner", PAIRS)
def test_fixed_rounds_are_unrevealed_and_refreshable(client, number, left, left_km, right, right_km, winner):
    url = f"/?round={number}"
    response = client.get(url)
    assert response.status_code == 200
    panel = quiz(response)
    assert f"Round {number} of 3" in panel
    assert "Which planet has the larger diameter?" in panel
    assert re.search(r'<form\b[^>]*action="/"[^>]*method="get"', panel)
    assert f'<input type="hidden" name="round" value="{number}">' in panel
    choices = re.findall(r'<button type="submit" name="choice" value="(\w+)">([^<]+)</button>', panel)
    assert choices == [(left, left.title()), (right, right.title())]
    assert "Correct" not in panel and "Try the next pair" not in panel
    assert f"{left_km:,} km" not in panel and f"{right_km:,} km" not in panel
    assert "quiz-next" not in panel
    assert quiz(client.get(url)) == panel
    assert "set-cookie" not in response.headers


@pytest.mark.parametrize("number,left,left_km,right,right_km,winner", PAIRS)
@pytest.mark.parametrize("side", ["left", "right"])
def test_each_answer_reveals_values_and_next_wraps(client, number, left, left_km, right, right_km, winner, side):
    choice = left if side == "left" else right
    url = f"/?round={number}&choice={choice}"
    response = client.get(url)
    assert response.status_code == 200
    panel = quiz(response)
    expected = "Correct" if choice == winner else "Try the next pair"
    other = "Try the next pair" if choice == winner else "Correct"
    assert expected in panel and other not in panel
    assert 'role="status"' in panel
    assert f"{left.title()}: {left_km:,} km" in panel
    assert f"{right.title()}: {right_km:,} km" in panel
    assert f"{winner.title()} has the larger diameter." in panel
    assert f"You chose {choice.title()}." in panel
    assert quiz(client.get(url)) == panel
    link = re.search(r'<a class="quiz-next" href="([^"]+)">Next</a>', panel)
    assert link and link.group(1) == f"/?round={number % 3 + 1}"
    next_panel = quiz(client.get(link.group(1)))
    assert f"Round {number % 3 + 1} of 3" in next_panel
    assert "Correct" not in next_panel and "Try the next pair" not in next_panel


@pytest.mark.parametrize("params,message", [
    ({"round": value}, "Choose a round from 1 through 3.")
    for value in ("0", "4", "-1", "1.5", "abc", "", "<script>")
] + [
    ({"round": "2", "choice": value}, "Choose one of the two planets in this round.")
    for value in ("jupiter", "pluto", "", "Mars", "<script>")
])
def test_invalid_quiz_input_has_clear_validation(client, params, message):
    response = client.get("/", params=params)
    assert response.status_code == 422
    panel = quiz(response)
    assert 'role="alert"' in panel and message in panel
    assert "Correct" not in panel and "Try the next pair" not in panel
    assert "<script>" not in response.text
    assert 'href="/?round=1"' in panel


def test_default_round_and_choice_without_round(client):
    assert quiz(client.get("/")) == quiz(client.get("/?round=1"))
    assert "Correct" in quiz(client.get("/?choice=jupiter"))
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/convert?value=1&src=km&dst=mi").json() == {"value": 0.6214, "unit": "mi"}
