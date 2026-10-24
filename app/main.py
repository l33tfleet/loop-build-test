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
LEADER_BELOW = 20  # circles under this % of the frame are too small to hold a label
CROWDED = 12  # big circles whose tops are this close get labels on opposite sides of the rim
LEADER_STEP = 11  # vertical spacing (% of frame) between leader-line labels


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
        p["label"], p["label_y"] = "leader", 5 + LEADER_STEP * i
    return scale


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    planets = sorted(SNAPSHOT["planets"], key=lambda p: p["order"])
    largest = max(planets, key=lambda p: p["diameter_km"])
    # Linear scale: each circle's diameter is diameter / largest diameter, so the largest planet fills the track.
    scale = [{**p, "width_pct": round(100 * p["diameter_km"] / largest["diameter_km"], 4)} for p in planets]
    scale = _place_labels(scale)
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
