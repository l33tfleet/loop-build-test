"""Diameter scale: all eight planets as overlapping circles or bars on one linear scale."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
from app.scale_labels import place_labels, to_scale


def context(state):
    planets = state["planets"]
    largest = max(planets, key=lambda p: p["diameter_km"])
    scale = to_scale(planets, largest["diameter_km"])
    return {"scale": place_labels(scale), "largest": largest}
