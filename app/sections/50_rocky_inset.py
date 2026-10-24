"""Rocky inset: the four rocky planets zoomed in, scaled to Earth instead of the largest planet."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
from app.scale_labels import place_labels

ROCKY = ("Mercury", "Venus", "Earth", "Mars")


def context(state):
    earth = state["earth"]
    # Inset: the rocky planets on their own linear scale, diameter / Earth's diameter, so Earth fills the panel.
    rocky = [{**p, "width_pct": round(100 * p["diameter_km"] / earth["diameter_km"], 4)}
             for p in state["planets"] if p["name"] in ROCKY]
    return {"rocky": place_labels(rocky)}
