"""Solar Arcade: a toy planet playground for exercising an autonomous build loop end to end."""
import json
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
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


@app.get("/", response_class=HTMLResponse)
def home(request: Request, age: str | None = None):
    planets = sorted(SNAPSHOT["planets"], key=lambda p: p["order"])
    largest = max(planets, key=lambda p: p["diameter_km"])
    # Linear scale: each circle's diameter is diameter / largest diameter, so the largest planet fills the track.
    scale = [{**p, "width_pct": round(100 * p["diameter_km"] / largest["diameter_km"], 4)} for p in planets]
    context = {"planets": planets, "scale": scale, "largest": largest, "source": SNAPSHOT["source"]}
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
    return templates.TemplateResponse(request, "index.html", context)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True}


@app.get("/convert")
def convert(value: float, src: str, dst: str) -> dict:
    factor = FACTORS.get((src, dst))
    if factor is None:
        raise HTTPException(400, f"unsupported conversion {src} -> {dst}")
    return {"value": round(value * factor, 4), "unit": dst}
