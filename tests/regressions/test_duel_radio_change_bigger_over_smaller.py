"""#63 on top of #62: a tapped duel radio swaps in the bigger-over-smaller ratio line in place.

Replaces the three #62 checks that pinned the old "<Left>'s diameter is N times <Right>'s." wording.
Reuses the Node harness and helpers from test_duel_radio_change_updates_in_place.py.
"""
import importlib.util
import re
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "duel_radio_change_updates_in_place", Path(__file__).with_name("test_duel_radio_change_updates_in_place.py")
)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
BASE, run, ratio, change, text = _base.BASE, _base.run, _base.ratio, _base.change, _base.text


def test_tapping_second_planet_updates_portraits_and_bigger_first_ratio_in_place(client):
    start = client.get("/").text
    assert 'data-planet="jupiter"' in start
    log = run(client, [
        {"do": "scrollTo", "y": 120},
        {"do": "measure", "region": "planet-duel", "as": "before"},
        change("right", "neptune", "earth", "neptune"),
        {"do": "respond"},
        {"do": "measure", "region": "planet-duel", "as": "after"},
    ], ["/?left=earth&right=neptune"])
    assert log.get("requested") == 1
    assert log["fetched"] == ["/?left=earth&right=neptune"]
    assert log["navigated"] == []
    assert log["pushed"] == [BASE + "/?left=earth&right=neptune"]
    duel = log["regions"]["planet-duel"]
    assert 'data-planet="neptune"' in duel
    assert 'data-planet="jupiter"' not in duel
    assert "<strong>Neptune</strong>" in duel
    assert ratio(duel) == "Neptune is 3.9 times as wide as Earth."
    assert log["after"] == log["before"]
    assert log["scrollY"] == 120


def test_tapping_first_planet_names_the_new_pair_bigger_first(client):
    log = run(client, [
        {"do": "scrollTo", "y": 60},
        change("left", "saturn", "saturn", "mercury"),
        {"do": "respond"},
    ], ["/?left=saturn&right=mercury"], start="/?left=earth&right=mercury")
    duel = log["regions"]["planet-duel"]
    assert ratio(duel) == "Saturn is 24.7 times as wide as Mercury."
    assert "<strong>Saturn</strong>" in duel
    assert log["scrollY"] == 60


def test_tapping_the_smaller_planet_second_still_puts_the_bigger_first(client):
    log = run(client, [
        change("right", "mercury", "neptune", "mercury"),
        {"do": "respond"},
    ], ["/?left=neptune&right=mercury"])
    assert ratio(log["regions"]["planet-duel"]) == "Neptune is 10.2 times as wide as Mercury."


def test_compare_button_stays_as_the_no_js_fallback(client):
    page = client.get("/").text
    form = re.search(r'<form class="duel-form" action="/" method="get">(.*?)</form>', page, re.DOTALL)
    assert form, "duel form must stay a plain GET form to /"
    assert '<button type="submit">Compare</button>' in form.group(1)
    without_js = client.get("/?left=earth&right=neptune").text
    assert "Neptune is 3.9 times as wide as Earth." in text(without_js)
    assert "Earth's diameter is" not in text(without_js)
    assert 'data-planet="neptune"' in without_js
