"""Planet diameter quiz: three rounds, each picking the larger of two planets."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
from app.scale_labels import to_scale

QUIZ_PAIRS = (("jupiter", "earth"), ("mercury", "mars"), ("neptune", "uranus"))


def _quiz(planets, round_number, choice):
    """All quiz state comes from the URL and the fixed planet snapshot."""
    if round_number not in ("1", "2", "3"):
        return {"error": "Choose a round from 1 through 3."}
    number = int(round_number)
    pair = QUIZ_PAIRS[number - 1]
    if choice is not None and choice not in pair:
        return {"error": "Choose one of the two planets in this round."}
    by_slug = {p["name"].lower(): p for p in planets}
    winner = max((by_slug[slug] for slug in pair), key=lambda p: p["diameter_km"])
    sides = to_scale((by_slug[slug] for slug in pair), winner["diameter_km"])
    return {"number": number, "sides": sides, "choice": by_slug[choice] if choice else None,
            "winner": winner, "correct": choice == winner["name"].lower(), "next": number % 3 + 1}


def context(state):
    params = state["params"]
    quiz = _quiz(state["planets"], params.get("round", "1"), params.get("choice"))
    return {"quiz": quiz, "status_code": 422} if "error" in quiz else {"quiz": quiz}
