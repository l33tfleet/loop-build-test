"""Solar Arcade: a toy planet playground for exercising an autonomous build loop end to end."""
import json
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


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    planets = sorted(SNAPSHOT["planets"], key=lambda p: p["order"])
    largest = max(planets, key=lambda p: p["diameter_km"])
    # Linear scale: each bar is diameter / largest diameter, so the largest planet fills the track.
    scale = [{**p, "width_pct": round(100 * p["diameter_km"] / largest["diameter_km"], 4)} for p in planets]
    context = {"planets": planets, "scale": scale, "largest": largest, "source": SNAPSHOT["source"]}
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
