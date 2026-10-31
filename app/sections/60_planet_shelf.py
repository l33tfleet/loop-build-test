"""Planet shelf: a card per planet, in the order the sort control picks."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention

# Insertion order controls the options and the default for missing or invalid sorts.
# Keys receive request state so year sorting uses this request's orbital periods.
SORTS = {
    "sun": {
        "label": "Sun order",
        "note": "In order from the Sun",
        "key": lambda p, state: (p["order"], p["name"].lower()),
    },
    "diameter": {
        "label": "Largest diameter first",
        "note": "Largest diameter first",
        "rank": "widest",
        "key": lambda p, state: (-p["diameter_km"], p["name"].lower()),
    },
    "year": {
        "label": "Shortest year first",
        "note": "Shortest year first",
        "rank": "shortest year",
        "key": lambda p, state: (state["periods"][p["name"]], p["name"].lower()),
    },
}


def context(state):
    sort = state["sort"] if state["sort"] in SORTS else next(iter(SORTS))
    key = SORTS[sort]["key"]
    label = SORTS[sort].get("rank")
    ordered = sorted(state["planets"], key=lambda p: key(p, state))
    return {
        "sort": sort,
        "SORTS": SORTS,
        "shelf": [
            {**p, "rank": i, "rank_label": label} for i, p in enumerate(ordered, start=1)
        ],
    }
