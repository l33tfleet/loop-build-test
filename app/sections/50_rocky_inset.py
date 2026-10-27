"""Rocky inset: the four rocky planets zoomed in, scaled to Earth instead of the largest planet."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
from app.scale_labels import place_labels, to_scale

ROCKY = ("Mercury", "Venus", "Earth", "Mars")


def context(state):
    earth = state["earth"]
    rocky = to_scale((p for p in state["planets"] if p["name"] in ROCKY), earth["diameter_km"])
    return {"rocky": place_labels(rocky)}
