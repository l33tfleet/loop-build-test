"""Shared scale and lookup contracts preserve current section output (#109)."""

from copy import deepcopy
from hashlib import sha256  # noqa: F401 -- preserved under the append-only supersession policy
from importlib import import_module
from unittest.mock import Mock

import pytest

from app import scale_labels


def test_scale_generator_preserves_order_fields_and_source():
    planets = [
        {"name": "Earth", "diameter_km": 12756, "width_pct": -1, "metadata": {}},
        {"name": "Mercury", "diameter_km": 4879, "order": 1},
    ]
    original = deepcopy(planets)

    scaled = scale_labels.to_scale((p for p in planets), 12756)

    assert scaled == [{**planets[0], "width_pct": 100.0}, {**planets[1], "width_pct": 38.2487}]
    assert all(copy is not source for copy, source in zip(scaled, planets, strict=True))
    assert scaled[0]["metadata"] is planets[0]["metadata"]
    scale_labels.place_labels(scaled)
    assert planets == original


def test_scale_has_no_minimum_floor():
    planets = ({"diameter_km": diameter} for diameter in (0, 1, 200000))
    assert [p["width_pct"] for p in scale_labels.to_scale(planets, 142984)] == [0.0, 0.0007, 139.8758]


def test_slug_lookup_preserves_original_dictionary_identity():
    earth = {"name": "Earth", "diameter_km": 12756}
    mercury = {"name": "MeRCuRy", "diameter_km": 4879}

    lookup = scale_labels.by_slug(p for p in (earth, mercury))

    assert list(lookup) == ["earth", "mercury"]
    assert lookup["earth"] is earth
    assert lookup["mercury"] is mercury


@pytest.mark.parametrize("section", ["10_planet_duel", "20_planet_quiz"])
def test_duel_and_quiz_use_shared_slug_lookup(monkeypatch, client, section):
    module = import_module(f"app.sections.{section}")
    lookup = Mock(wraps=scale_labels.by_slug)
    monkeypatch.setattr(module, "by_slug", lookup)

    assert client.get("/?left=mars&right=earth&round=1&choice=earth").status_code == 200
    lookup.assert_called_once()


@pytest.mark.parametrize("section", [
    "10_planet_duel", "20_planet_quiz", "40_diameter_scale", "50_rocky_inset",
])
def test_all_scale_consumers_use_shared_helper(monkeypatch, client, section):
    module = import_module(f"app.sections.{section}")
    scaling = Mock(wraps=scale_labels.to_scale)
    monkeypatch.setattr(module, "to_scale", scaling)

    assert client.get("/").status_code == 200
    scaling.assert_called_once()
