"""Solar Arcade: a toy planet playground for exercising an autonomous build loop end to end."""
import json
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Solar Arcade")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")

FACTORS = {("km", "mi"): 0.621371, ("mi", "km"): 1.609344, ("kg", "lb"): 2.204623, ("lb", "kg"): 0.453592}
SNAPSHOT = json.loads((ROOT / "data" / "planets.json").read_text())
# Approximate orbital periods in Earth days, used for the toy year conversion.
ORBITAL_PERIOD_DAYS = {
    "Mercury": 88.0, "Venus": 224.7, "Earth": 365.2, "Mars": 687.0,
    "Jupiter": 4331.0, "Saturn": 10747.0, "Uranus": 30589.0, "Neptune": 59800.0,
}
LEADER_BELOW = 20  # circles under this % of the frame are too small to hold a label
CROWDED = 12  # big circles whose tops are this close get labels on opposite sides of the rim
ROCKY = ("Mercury", "Venus", "Earth", "Mars")  # zoomed inset, scaled to Earth instead of the largest planet
LEADER_STEP = 13  # vertical spacing (% of frame) between leader-line labels; fits two text lines at 320px
QUIZ_PAIRS = (("jupiter", "earth"), ("mercury", "mars"), ("neptune", "uranus"))


def _ordinal(n):
    """1 -> '1st', 2 -> '2nd', 11 -> '11th', 23 -> '23rd'."""
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _earths(diameter_km, earth_km):
    """Diameter in Earths to 2 significant figures: 0.38, 4.0, 11; Earth itself is exactly 1."""
    ratio = diameter_km / earth_km
    return "1" if ratio == 1 else f"{ratio:#.2g}".rstrip(".")


def _place_labels(scale):
    """Label the overlapping circles: big ones on their rim, small ones on leader lines."""
    by_size = sorted(scale, key=lambda p: p["width_pct"], reverse=True)
    for z, p in enumerate(by_size, start=1):
        p["z"] = z  # larger circles sit behind smaller ones
    big = [p for p in by_size if p["width_pct"] >= LEADER_BELOW]
    for p, smaller in zip(big, big[1:] + [None]):
        crowded = smaller is not None and p["width_pct"] - smaller["width_pct"] < CROWDED
        p["label"], p["label_y"] = ("above" if crowded else "inside"), p["width_pct"]
    small = [p for p in reversed(by_size) if p["width_pct"] < LEADER_BELOW]
    for i, p in enumerate(small):
        p["label"], p["label_y"] = "leader", 7 + LEADER_STEP * i
    return scale


def _duel(planets, left, right):
    """Two planets side by side at the same large portrait size; ratio is left / right to one decimal."""
    by_slug = {p["name"].lower(): p for p in planets}
    if left not in by_slug or right not in by_slug:
        return {"left": "jupiter", "right": "earth",
                "error": "Choose two planets from the lists: unknown planet name."}
    a, b = by_slug[left], by_slug[right]
    return {"left": left, "right": right, "sides": [a, b], "ratio": f"{a['diameter_km'] / b['diameter_km']:.1f}"}


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
    # Linear, no floor: each circle's diameter is diameter / the larger one's, so Jupiter is ~11 Earths wide.
    sides = [{**by_slug[slug], "width_pct": round(100 * by_slug[slug]["diameter_km"] / winner["diameter_km"], 4)}
             for slug in pair]
    return {"number": number, "sides": sides, "choice": by_slug[choice] if choice else None,
            "winner": winner, "correct": choice == winner["name"].lower(), "next": number % 3 + 1}


@app.get("/", response_class=HTMLResponse)
def home(request: Request, age: str | None = None, sort: str = "sun", left: str = "jupiter", right: str = "earth",
         round_number: str = Query("1", alias="round"), choice: str | None = None):
    sort_keys = {
        "sun": lambda p: (p["order"], p["name"].lower()),
        "diameter": lambda p: (-p["diameter_km"], p["name"].lower()),
        "year": lambda p: (ORBITAL_PERIOD_DAYS[p["name"]], p["name"].lower()),
    }
    if sort not in sort_keys:
        sort = "sun"
    earth = next(p for p in SNAPSHOT["planets"] if p["name"] == "Earth")
    planets = [{**p, "ordinal": _ordinal(p["order"]), "earths": _earths(p["diameter_km"], earth["diameter_km"])}
               for p in sorted(SNAPSHOT["planets"], key=sort_keys["sun"])]
    largest = max(planets, key=lambda p: p["diameter_km"])
    # Linear scale: each circle's diameter is diameter / largest diameter, so the largest planet fills the track.
    scale = [{**p, "width_pct": round(100 * p["diameter_km"] / largest["diameter_km"], 4)} for p in planets]
    scale = _place_labels(scale)
    # Inset: the rocky planets on their own linear scale, diameter / Earth's diameter, so Earth fills the panel.
    rocky = [{**p, "width_pct": round(100 * p["diameter_km"] / earth["diameter_km"], 4)}
             for p in planets if p["name"] in ROCKY]
    rocky = _place_labels(rocky)
    context = {"planets": sorted(planets, key=sort_keys[sort]), "sort": sort,
               "scale": scale, "largest": largest, "rocky": rocky, "earth": earth,
               "source": SNAPSHOT["source"]}
    birthdays = []
    age_error = None
    if age is not None:
        try:
            earth_age = float(age)
            if not math.isfinite(earth_age) or not 0 <= earth_age <= 120:
                raise ValueError
        except ValueError:
            age_error = "Enter a finite Earth age from 0 through 120."
        else:
            # Normalize signed zero so every zero result displays as 0.0.
            earth_age = earth_age or 0.0
            for planet in planets:
                name = planet["name"]
                # Earth's ratio is exactly one; avoid float round-trip rounding drift.
                years = earth_age if name == "Earth" else (
                    earth_age * ORBITAL_PERIOD_DAYS["Earth"] / ORBITAL_PERIOD_DAYS[name]
                )
                birthdays.append({"name": name, "years": f"{years:.1f}"})
    context.update(age=age if age is not None else "", age_error=age_error, birthdays=birthdays)
    context["duel"] = _duel(planets, left, right)
    context["quiz"] = _quiz(planets, round_number, choice)
    status = 422 if "error" in context["duel"] or "error" in context["quiz"] else 200
    return templates.TemplateResponse(request, "index.html", context, status_code=status)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/convert")
def convert(value: float, src: str, dst: str) -> dict:
    factor = FACTORS.get((src, dst))
    if factor is None:
        raise HTTPException(400, f"unsupported conversion {src} -> {dst}")
    return {"value": round(value * factor, 4), "unit": dst}
