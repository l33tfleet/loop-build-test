"""URL state the home page sections share, parsed once per request."""


def _ordinal(n):
    """1 -> '1st', 2 -> '2nd', 11 -> '11th', 23 -> '23rd'."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _earths(diameter_km, earth_km):
    """Diameter in Earths to 2 significant figures: 0.38, 4.0, 11; Earth itself is exactly 1."""
    ratio = diameter_km / earth_km
    return "1" if ratio == 1 else f"{ratio:#.2g}".rstrip(".")


def build(params, snapshot, periods):
    """Shared state: query parameters plus the planet snapshot every section reads.

    `age` and `sort` are raw query values (None when absent); sections validate them.
    `params` keeps the raw query so a section can read parameters only it uses.
    """
    earth = next(p for p in snapshot["planets"] if p["name"] == "Earth")
    planets = [{**p, "ordinal": _ordinal(p["order"]), "earths": _earths(p["diameter_km"], earth["diameter_km"])}
               for p in sorted(snapshot["planets"], key=lambda p: (p["order"], p["name"].lower()))]
    return {
        "params": params,
        "age": params.get("age"),
        "sort": params.get("sort"),
        "planets": planets,  # Sun order
        "earth": earth,
        "periods": periods,  # orbital period in Earth days, by planet name
        "source": snapshot["source"],
    }
