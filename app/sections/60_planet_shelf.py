"""Planet shelf: a card per planet, in the order the sort control picks."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention


def context(state):
    periods = state["periods"]
    sort_keys = {
        "sun": lambda p: (p["order"], p["name"].lower()),
        "diameter": lambda p: (-p["diameter_km"], p["name"].lower()),
        "year": lambda p: (periods[p["name"]], p["name"].lower()),
    }
    return {"shelf": sorted(state["planets"], key=sort_keys[state["sort"]])}
