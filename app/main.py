"""Solar Arcade: a toy planet playground for exercising an autonomous build loop end to end."""
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app import page_state, sections

ROOT = Path(__file__).resolve().parent.parent
app = FastAPI(title="Solar Arcade")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")
SECTIONS_PACKAGE = sections  # home page sections: app/sections/NN_name.py, in filename order

FACTORS = {("km", "mi"): 0.621371, ("mi", "km"): 1.609344, ("kg", "lb"): 2.204623, ("lb", "kg"): 0.453592}
SNAPSHOT = json.loads((ROOT / "data" / "planets.json").read_text())
# Approximate orbital periods in Earth days, used for the toy year conversion.
ORBITAL_PERIOD_DAYS = {
    "Mercury": 88.0, "Venus": 224.7, "Earth": 365.2, "Mars": 687.0,
    "Jupiter": 4331.0, "Saturn": 10747.0, "Uranus": 30589.0, "Neptune": 59800.0,
}


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    state = page_state.build(request.query_params, SNAPSHOT, ORBITAL_PERIOD_DAYS)
    context = {k: v for k, v in state.items() if k not in ("params", "periods", "sort")}
    status = 200
    found = sections.discover(SECTIONS_PACKAGE)
    for section in found:
        section_context = dict(section.context(state))
        status = max(status, section_context.pop("status_code", 200))
        clash = context.keys() & section_context.keys()
        if clash:
            raise RuntimeError(f"{section.template} reuses context names {sorted(clash)}")
        context.update(section_context)
    context["sections"] = [section.template for section in found]
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
