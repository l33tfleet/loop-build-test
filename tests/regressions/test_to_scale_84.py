"""Shared linear scaling preserves planet data and the existing diameter ratios."""

from copy import deepcopy

from app.scale_labels import to_scale


def test_to_scale_ratios_and_independent_copies():
    planets = [
        {"name": "Jupiter", "diameter_km": 142984, "color": "tan"},
        {"name": "Earth", "diameter_km": 12756, "color": "blue", "width_pct": -1},
    ]
    original = deepcopy(planets)

    scaled = to_scale(planets, 142984)

    assert scaled == [
        {**planets[0], "width_pct": 100.0},
        {**planets[1], "width_pct": 8.9213},
    ]
    assert planets == original
    assert all(copy is not source for copy, source in zip(scaled, planets, strict=True))
    scaled[0]["name"] = "Changed"
    assert planets == original


def test_to_scale_is_linear_without_a_floor():
    planets = [{"diameter_km": 0}, {"diameter_km": 1}, {"diameter_km": 200000}]

    assert [p["width_pct"] for p in to_scale(planets, 142984)] == [0.0, 0.0007, 139.8758]
