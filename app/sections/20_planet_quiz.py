"""Planet diameter quiz: each round picks the larger of two planets."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
from app.scale_labels import to_scale

QUIZ_PAIRS = (("jupiter", "earth"), ("mercury", "mars"), ("neptune", "uranus"))
QUIZ_SETS = (
    QUIZ_PAIRS,
    (("saturn", "neptune"), ("venus", "mercury"), ("earth", "mars")),
    (("uranus", "saturn"), ("mars", "venus"), ("venus", "earth")),
)


def _quiz(planets, round_number, choice, score, pairs):
    """All quiz state comes from the URL and the fixed planet snapshot."""
    rounds = len(pairs)
    if round_number not in {str(number) for number in range(1, rounds + 1)}:
        return {"error": f"Choose a round from 1 through {rounds}."}
    number = int(round_number)
    pair = pairs[number - 1]
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
    params = state["params"]
    set_id = params.get("set", "0")
    if set_id not in {str(number) for number in range(len(QUIZ_SETS))}:
        return {"quiz": {"error": "Choose a supported quiz set."}, "status_code": 422}
    set_number = int(set_id)
    # Keep QUIZ_PAIRS as the source of the default game's rounds.
    pairs = QUIZ_PAIRS if set_number == 0 else QUIZ_SETS[set_number]
    rounds = len(pairs)
    raw_score = params.get("score")
    score = int(raw_score) if raw_score in {str(number) for number in range(rounds + 1)} else 0
    quiz = _quiz(state["planets"], params.get("round", "1"), params.get("choice"), score, pairs)
    quiz["set_id"] = set_id if "set" in params else None
    quiz["replay_url"] = f"/?round=1&set={(set_number + 1) % len(QUIZ_SETS)}"
    if "error" not in quiz:
        quiz["next_url"] = f"/?round={quiz['next']}&score={quiz['resulting_score']}"
        if "set" in params:
            quiz["next_url"] += f"&set={set_id}"
    return {"quiz": quiz, "status_code": 422} if "error" in quiz else {"quiz": quiz}
