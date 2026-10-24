"""Diameter scale: all eight planets as overlapping circles or bars on one linear scale."""
# ruff: noqa: N999 -- the NN_ prefix is the section's place on the page, by convention
from app.scale_labels import place_labels


def context(state):
    planets = state["planets"]
    largest = max(planets, key=lambda p: p["diameter_km"])
    # Linear scale: each circle's diameter is diameter / largest diameter, so the largest planet fills the track.
    scale = [{**p, "width_pct": round(100 * p["diameter_km"] / largest["diameter_km"], 4)} for p in planets]
    return {"scale": place_labels(scale), "largest": largest}
