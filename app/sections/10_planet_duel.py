"""Planet size duel: two planets side by side drawn to true scale."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
from app.scale_labels import by_slug, to_scale

DEFAULT_PAIR = ("jupiter", "earth")


def context(state):
    """Return a duel dict with scaled sides and ratio, or an error and status_code=422.

    Read raw params, falling back to legacy top-level picks when params is absent.
    """
    lookup = by_slug(state["planets"])
    params = state.get("params", state)
    left = params.get("left", DEFAULT_PAIR[0])
    right = params.get("right", DEFAULT_PAIR[1])
    if left not in lookup or right not in lookup:
        return {"duel": {"left": DEFAULT_PAIR[0], "right": DEFAULT_PAIR[1],
                         "error": "Choose two planets from the lists: unknown planet name."},
                "status_code": 422}
    a, b = lookup[left], lookup[right]
    largest = max(a["diameter_km"], b["diameter_km"])
    sides = to_scale((a, b), largest)
    big, small = sorted((a, b), key=lambda p: p["diameter_km"], reverse=True)
    ratio = big["diameter_km"] / small["diameter_km"]
    formatted_ratio = format(ratio, ".2f" if ratio < 2 else ".1f")
    return {"duel": {"left": left, "right": right, "sides": sides, "same": left == right, "big": big["name"],
                     "small": small["name"], "ratio": formatted_ratio}}
