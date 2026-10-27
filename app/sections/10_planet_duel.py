"""Planet size duel: two planets side by side drawn to true scale."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
from app.scale_labels import to_scale


def context(state):
    """Ratio is bigger / smaller to one decimal."""
    by_slug = {p["name"].lower(): p for p in state["planets"]}
    left, right = state["left"], state["right"]
    if left not in by_slug or right not in by_slug:
        return {"duel": {"left": "jupiter", "right": "earth",
                         "error": "Choose two planets from the lists: unknown planet name."},
                "status_code": 422}
    a, b = by_slug[left], by_slug[right]
    largest = max(a["diameter_km"], b["diameter_km"])
    sides = to_scale((a, b), largest)
    big, small = sorted((a, b), key=lambda p: p["diameter_km"], reverse=True)
    return {"duel": {"left": left, "right": right, "sides": sides, "same": left == right, "big": big["name"],
                     "small": small["name"], "ratio": f"{big['diameter_km'] / small['diameter_km']:.1f}"}}
