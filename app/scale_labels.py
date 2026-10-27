"""Label placement for overlapping planet circles, shared by the diameter scale and the rocky inset."""

LEADER_BELOW = 20  # circles under this % of the frame are too small to hold a label
CROWDED = 12  # big circles whose tops are this close get labels on opposite sides of the rim
LEADER_STEP = 13  # vertical spacing (% of frame) between leader-line labels; fits two text lines at 320px


def to_scale(planets, reference_km):
    """Return ordered shallow copies with linear widths and no floor.

    width_pct = round(100 * diameter_km / reference_km, 4), rounded to four decimals.
    """
    return [{**p, "width_pct": round(100 * p["diameter_km"] / reference_km, 4)} for p in planets]


def place_labels(scale):
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
