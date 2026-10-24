"""#68: once a round is answered the two answer buttons lock, the pick is marked, and a miss reads "Not quite"."""
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


def buttons(panel):
    form = re.search(r"<form\b.*?</form>", panel, re.DOTALL)
    assert form, "Quiz form missing"
    return re.findall(r"<button\b([^>]*)>(.*?)</button>", form.group(0), re.DOTALL)


def test_answered_round_disables_both_buttons_and_marks_earth(client):
    panel = quiz(client.get("/?round=1&choice=earth"))
    found = buttons(panel)
    assert len(found) == 2
    for attrs, _ in found:
        assert re.search(r"\bdisabled\b", attrs)
    (jupiter_attrs, jupiter_body), (earth_attrs, earth_body) = found
    assert 'value="jupiter"' in jupiter_attrs and 'value="earth"' in earth_attrs
    assert 'aria-pressed="true"' in earth_attrs
    assert 'aria-pressed="false"' in jupiter_attrs
    assert "Your pick" in earth_body and "Your pick" not in jupiter_body
    assert "Earth" in earth_body


def test_unanswered_round_keeps_both_buttons_enabled(client):
    found = buttons(quiz(client.get("/?round=1")))
    assert len(found) == 2
    for attrs, body in found:
        assert "disabled" not in attrs
        assert "aria-pressed" not in attrs
        assert "Your pick" not in body


@pytest.mark.parametrize("number,left,left_km,right,right_km,winner", PAIRS)
@pytest.mark.parametrize("side", ["left", "right"])
def test_each_answer_reveals_values_and_next_wraps(client, number, left, left_km, right, right_km, winner, side):
    choice = left if side == "left" else right
    url = f"/?round={number}&choice={choice}"
    response = client.get(url)
    assert response.status_code == 200
    panel = quiz(response)
    heading = re.search(r'<div class="quiz-answer" role="status">\s*<p><strong>([^<]+)</strong>', panel)
    assert heading and heading.group(1) == ("Correct" if choice == winner else "Not quite")
    assert "Try the next pair" not in panel
    assert ("Not quite" if choice == winner else "Correct") not in panel
    assert f"{left.title()}: {left_km:,} km" in panel
    assert f"{right.title()}: {right_km:,} km" in panel
    assert f"{winner.title()} has the larger diameter." in panel
    assert f"You chose {choice.title()}." in panel
    assert quiz(client.get(url)) == panel
    for attrs, body in buttons(panel):
        assert re.search(r"\bdisabled\b", attrs)
        assert ("Your pick" in body) == (f'value="{choice}"' in attrs)
    link = re.search(r'<a class="quiz-next" href="([^"]+)">Next</a>', panel)
    assert link and link.group(1) == f"/?round={number % 3 + 1}"
    next_panel = quiz(client.get(link.group(1)))
    assert f"Round {number % 3 + 1} of 3" in next_panel
    assert "Correct" not in next_panel and "Not quite" not in next_panel
    assert all("disabled" not in attrs for attrs, _ in buttons(next_panel))
