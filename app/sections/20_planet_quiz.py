"""Planet diameter quiz: each round picks the larger of two planets."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
from app.scale_labels import to_scale

QUIZ_PAIRS = (("jupiter", "earth"), ("mercury", "mars"), ("neptune", "uranus"))


def _quiz(planets, round_number, choice, score, rounds):
    """All quiz state comes from the URL and the fixed planet snapshot."""
    if round_number not in {str(number) for number in range(1, rounds + 1)}:
        return {"error": f"Choose a round from 1 through {rounds}."}
    number = int(round_number)
    pair = QUIZ_PAIRS[number - 1]
    if choice is not None and choice not in pair:
        return {"error": "Choose one of the two planets in this round."}
    by_slug = {p["name"].lower(): p for p in planets}
    winner = max((by_slug[slug] for slug in pair), key=lambda p: p["diameter_km"])
    sides = to_scale((by_slug[slug] for slug in pair), winner["diameter_km"])
    correct = choice == winner["name"].lower()
    return {"number": number, "rounds": rounds, "sides": sides,
            "choice": by_slug[choice] if choice else None,
            "winner": winner, "correct": correct, "next": number + 1,
            "score": score, "resulting_score": min(rounds, score + correct),
            "complete": number == rounds and choice is not None}


def context(state):
    ROUNDS = len(QUIZ_PAIRS)
    params = state["params"]
    raw_score = params.get("score")
    score = int(raw_score) if raw_score in {str(number) for number in range(ROUNDS + 1)} else 0
    quiz = _quiz(state["planets"], params.get("round", "1"), params.get("choice"), score, ROUNDS)
    return {"quiz": quiz, "status_code": 422} if "error" in quiz else {"quiz": quiz}
