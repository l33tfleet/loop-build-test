"""Shelf card h3 semantics, retaining superseded content, sorting and layout coverage."""

import json
import re
from html import unescape

import pytest
from test_card_ordinal_earths import ORDINALS, SNAPSHOT
from test_planet_shelf import CARD, EXPECTED_KM, SUN_ORDER
from test_planet_sort import Controls
from test_shelf_heading import _shelf
from test_shelf_two_per_row_phone import (
    BODY_PAD,
    BOLD_FUDGE,
    BORDER,
    FUDGE,
    LINES,
    _columns,
    _decl,
    _px,
    _text_px,
)

from app import main


def _cards(html):
    return [
        (unescape(re.search(r"<h3[^>]*>(.*?)</h3>", body, re.DOTALL).group(1)).strip(),
         unescape(re.search(r'class="diameter"[^>]*>(.*?)<', body, re.DOTALL).group(1)).strip())
        for body in CARD.findall(html)
    ]


def _card_text(client):
    return {
        unescape(re.search(r"<h3[^>]*>(.*?)</h3>", body, re.DOTALL).group(1)).strip():
        " ".join(unescape(re.sub(r"<[^>]+>", " ", body)).split())
        for body in CARD.findall(client.get("/").text)
    }


def shelf_names(html):
    return re.findall(r'<article class="planet-card"[^>]*>\s*<h3>(.*?)</h3>', html)


def _card_lines(client):
    for body in CARD.findall(client.get("/").text):
        for selector, pattern, upper in LINES:
            selector, pattern = selector.replace("h2", "h3"), pattern.replace("h2", "h3")
            text = " ".join(unescape(re.search(pattern, body, re.DOTALL).group(1)).split())
            yield selector, text.upper() if upper else text


def test_planet_card_names_are_h3_under_section_h2(client):
    _, body = _shelf(client)
    cards = CARD.findall(body)
    assert len(cards) == 8
    assert re.findall(r'<h2\b[^>]*>(.*?)</h2>', body) == ["The eight planets"]
    assert [re.findall(r'<h3\b[^>]*>(.*?)</h3>', card) for card in cards] == [
        [name] for name in SUN_ORDER
    ]
    assert all(not re.search(r'<h2\b', card) for card in cards)


def test_home_shows_eight_cards_in_sun_order(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Solar Arcade" in r.text
    cards = _cards(r.text)
    assert [name for name, _ in cards] == SUN_ORDER



def test_cards_show_snapshot_diameters_with_unit(client):
    cards = dict(_cards(client.get("/").text))
    for name, km in EXPECTED_KM.items():
        assert cards[name] == f"{km:,} km"



@pytest.mark.parametrize("sort,expected", [
    ("sun", ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]),
    ("diameter", ["Jupiter", "Saturn", "Uranus", "Neptune", "Earth", "Venus", "Mars", "Mercury"]),
    ("year", ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]),
    ("unknown", ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]),
    ("", ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]),
])
def test_sort_order_and_active_choice_survive_reload(client, sort, expected):
    for _ in range(2):
        response = client.get("/", params={"sort": sort, "age": "30"})
        assert response.status_code == 200
        assert shelf_names(response.text) == expected
        tags = Controls(response.text).tags
        selected = [attrs["value"] for tag, attrs in tags if tag == "option" and "selected" in attrs]
        assert selected == [sort if sort in {"sun", "diameter", "year"} else "sun"]



@pytest.mark.parametrize("sort,field", [("sun", "order"), ("diameter", "diameter_km"), ("year", None)])
def test_sort_uses_stored_values_and_slug_ties(client, monkeypatch, sort, field):
    planets = [dict(p) for p in reversed(main.SNAPSHOT["planets"])]
    # All values tie except Mercury; neither snapshot order nor Sun order resolves the tie.
    if field:
        for planet in planets:
            planet[field] = 10 if planet["name"] == "Mercury" else 20
    else:
        monkeypatch.setattr(main, "ORBITAL_PERIOD_DAYS", {
            p["name"]: 10 if p["name"] == "Mercury" else 20 for p in planets
        })
    monkeypatch.setattr(main, "SNAPSHOT", {**main.SNAPSHOT, "planets": planets})
    tied = sorted(p["name"] for p in planets if p["name"] != "Mercury")
    expected = tied + ["Mercury"] if sort == "diameter" else ["Mercury"] + tied
    assert shelf_names(client.get("/", params={"sort": sort}).text) == expected



def test_cards_show_ordinal_from_the_sun_not_hash_rank(client):
    planets = json.loads(SNAPSHOT.read_text())["planets"]
    cards = _card_text(client)
    for p in planets:
        assert f"{ORDINALS[p['order'] - 1]} from the Sun" in cards[p["name"]]
        assert not re.search(r"#\d", cards[p["name"]])
    assert "1st from the Sun" in cards["Mercury"]
    assert "8th from the Sun" in cards["Neptune"]



def test_jupiter_and_mercury_say_how_many_earths_wide(client):
    cards = _card_text(client)
    assert "About 11 Earths wide" in cards["Jupiter"]
    assert "About 0.38 Earths wide" in cards["Mercury"]
    assert re.search(r"\b1 Earths? wide", cards["Earth"])



def test_earths_wide_follows_the_snapshot(client, monkeypatch):
    from app import main

    planets = [{**p, "diameter_km": p["diameter_km"] * 2} if p["name"] == "Mercury" else p
               for p in main.SNAPSHOT["planets"]]
    monkeypatch.setitem(main.SNAPSHOT, "planets", planets)
    assert "About 0.76 Earths wide" in _card_text(client)["Mercury"]



def test_heading_sits_directly_above_cards_outside_the_grid(client):
    _, body = _shelf(client)
    heading = body.index('<h2 id="shelf-title"')
    grid = body.index('<div class="shelf">')
    first_card = body.index('<article class="planet-card"')
    assert heading < grid < first_card
    # Nothing but the note between the heading block and the grid: no other cards or headings.
    assert body.count("<h2") == 1
    assert body.count("<h3") == 8
    assert "<article" not in body[:grid]



def test_card_text_fits_on_one_line_at_320_and_390(client):
    css = client.get("/static/arcade.css").text
    lines = list(_card_lines(client))
    assert ("h3", "Jupiter") in lines and (".earths", "About 0.38 Earths wide") in lines
    assert (".diameter", "142,984 km") in lines
    for viewport in (320, 390, 960 + 2 * BODY_PAD):
        _, col = _columns(css, viewport)
        pad = _px(_decl(css, viewport, ".planet-card", "padding"))
        inner = col - 2 * pad - 2 * BORDER
        for selector, text in lines:
            full = ".planet-card " + selector
            font = _px(_decl(css, viewport, full, "font-size"))
            spacing = _decl(css, viewport, full, "letter-spacing")
            spacing = float(spacing[:-2]) if spacing else 0.0
            need = _text_px(text, font, spacing) * (BOLD_FUDGE if selector == "h3" else FUDGE)
            assert need <= inner, f"{viewport}px: {text!r} needs {need:.0f}px, card has {inner:.0f}px"


@pytest.mark.parametrize("viewport,size", [(390, "1.2rem"), (992, "1.35rem")])
def test_card_heading_preserves_size_color_and_spacing(client, viewport, size):
    css = client.get("/static/arcade.css").text
    assert _decl(css, viewport, ".planet-card h3", "font-size") == size
    assert _decl(css, viewport, ".planet-card h3", "color") == "var(--paper)"
    assert _decl(css, viewport, ".planet-card h3", "margin") == "0 0 2px"


@pytest.mark.parametrize("sort", ["sun", "diameter", "year"])
def test_heading_outline_survives_shelf_sort(client, sort):
    html = client.get("/", params={"sort": sort}).text
    body = re.search(r'<section class="planet-shelf"[^>]*>(.*?)</section>', html, re.DOTALL).group(1)
    headings = re.findall(r'<h([23])\b[^>]*>(.*?)</h\1>', body)
    assert headings[0] == ("2", "The eight planets")
    assert len(headings) == 9
    assert all(level == "3" for level, _ in headings[1:])
    assert {name for _, name in headings[1:]} == set(SUN_ORDER)


def test_snapshot_planet_names_render_as_h3(client):
    names = [planet["name"] for planet in json.loads(SNAPSHOT.read_text())["planets"]]
    cards = CARD.findall(client.get("/").text)
    assert len(cards) == len(names) == 8
    assert [re.findall(r"<h3\b[^>]*>(.*?)</h3>", body) for body in cards] == [
        [name] for name in names
    ]


def test_diameter_sort_keeps_planet_names_as_h3(client):
    expected = [planet["name"] for planet in sorted(
        main.SNAPSHOT["planets"], key=lambda planet: -planet["diameter_km"]
    )]
    html = client.get("/", params={"sort": "diameter"}).text
    names = re.findall(r'<article class="planet-card"[^>]*>\s*<h3>(.*?)</h3>', html)
    assert names == expected
