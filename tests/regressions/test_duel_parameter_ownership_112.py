"""The duel owns its parameters and one default pair, preserving rendered HTML (#112)."""

import hashlib  # noqa: F401 -- preserved under the append-only supersession policy
import importlib

import pytest

from app.main import ORBITAL_PERIOD_DAYS, SNAPSHOT
from app.page_state import build

duel_section = importlib.import_module("app.sections.10_planet_duel")


@pytest.mark.parametrize("params", [{}, {"left": "mars", "right": "neptune"}])
def test_shared_state_leaves_duel_parameters_raw(params):
    state = build(params, SNAPSHOT, ORBITAL_PERIOD_DAYS)
    assert state["params"] == params
    assert "left" not in state
    assert "right" not in state


@pytest.mark.parametrize("params,expected", [
    ({"left": "mars", "right": "neptune"}, ("mars", "neptune")),
    ({}, ("jupiter", "earth")),
])
def test_raw_params_take_precedence_over_legacy_picks(params, expected):
    state = build(params, SNAPSHOT, ORBITAL_PERIOD_DAYS)
    state.update(left="venus", right="saturn")
    duel = duel_section.context(state)["duel"]
    assert (duel["left"], duel["right"]) == expected


@pytest.mark.parametrize("params", [{}, {"left": "mars"}, {"right": "mars"},
                                        {"left": "pluto"}, {"right": "pluto"}])
def test_default_pair_controls_defaults_and_invalid_reset(monkeypatch, params):
    monkeypatch.setattr(duel_section, "DEFAULT_PAIR", ("venus", "saturn"))
    result = duel_section.context(build(params, SNAPSHOT, ORBITAL_PERIOD_DAYS))
    invalid = "pluto" in params.values()
    expected = ("venus", "saturn") if invalid else (
        params.get("left", "venus"), params.get("right", "saturn"))
    assert (result["duel"]["left"], result["duel"]["right"]) == expected
    assert result.get("status_code", 200) == (422 if invalid else 200)
    assert ("error" in result["duel"]) == invalid
