"""#97: changing quiz pairs alone updates rounds, validation and scoring."""
import importlib
import re

import pytest


@pytest.fixture
def four_pairs(monkeypatch):
    module = importlib.import_module("app.sections.20_planet_quiz")
    monkeypatch.setattr(module, "QUIZ_PAIRS", (*module.QUIZ_PAIRS, ("earth", "mars")))


def panel(response):
    assert response.status_code == 200
    match = re.search(r'<section class="planet-quiz"[^>]*>(.*?)</section>', response.text, re.DOTALL)
    assert match
    return match[1]


def test_fourth_pair_updates_progress_and_ending(client, four_pairs):
    third = panel(client.get("/?round=3&choice=uranus&score=2"))
    assert "Round 3 of 4" in third
    assert 'href="/?round=4&amp;score=3">Next</a>' in third
    assert "Play again" not in third
    assert "You got" not in third

    fourth = panel(client.get("/?round=4&score=3"))
    assert "Round 4 of 4" in fourth
    assert 'name="score" value="3"' in fourth
    answered = panel(client.get("/?round=4&choice=earth&score=3"))
    assert "You got 4 of 4!" in answered
    assert ">Play again</a>" in answered
    assert ">Next</a>" not in answered


@pytest.mark.parametrize("value", ["5", "0", "04", "+4", " 4", "４", "4.0", "oops"])
def test_round_validation_uses_pair_count(client, four_pairs, value):
    response = client.get("/", params={"round": value})
    assert response.status_code == 422
    assert "Choose a round from 1 through 4." in response.text


@pytest.mark.parametrize("choice", ["earth", "mars"])
def test_score_four_is_accepted_and_capped(client, four_pairs, choice):
    answered = panel(client.get("/", params={"round": "4", "choice": choice, "score": "4"}))
    assert 'name="score" value="4"' in answered
    assert "You got 4 of 4!" in answered


@pytest.mark.parametrize("score", ["5", "04", "+4", " 4", "４", "4.0"])
def test_invalid_scores_normalize_with_four_pairs(client, four_pairs, score):
    answered = panel(client.get("/", params={"round": "4", "choice": "earth", "score": score}))
    assert 'name="score" value="0"' in answered
    assert "You got 1 of 4!" in answered
