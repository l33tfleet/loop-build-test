import json
import re
from html import unescape
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PLANETS = json.loads((ROOT / "data" / "planets.json").read_text())["planets"]
CARD = re.compile(r'<article class="planet-card"[^>]*>(.*?)</article>', re.DOTALL)
NAME = re.compile(r"<h3[^>]*>(.*?)</h3>", re.DOTALL)
BADGE = re.compile(r'<p class="rank">(.*?)</p>', re.DOTALL)


def _shelf(client, url):
    """Return (planet name, badge text or None) per card, in page order."""
    response = client.get(url)
    assert response.status_code == 200
    rows = []
    for body in CARD.findall(response.text):
        name = unescape(NAME.search(body).group(1)).strip()
        badge = BADGE.search(body)
        rows.append((name, unescape(badge.group(1)).strip() if badge else None))
    assert len(rows) == 8
    return rows


def _visible_card_text(client, url):
    return " ".join(
        unescape(re.sub(r"<[^>]+>", " ", body)) for body in CARD.findall(client.get(url).text)
    )


def test_diameter_sort_ranks_every_card_jupiter_to_mercury(client):
    rows = _shelf(client, "/?sort=diameter")
    names = [p["name"] for p in sorted(PLANETS, key=lambda p: -p["diameter_km"])]
    assert rows == [(name, f"#{i} widest") for i, name in enumerate(names, start=1)]
    assert rows[0] == ("Jupiter", "#1 widest")
    assert rows[-1] == ("Mercury", "#8 widest")


def test_year_sort_ranks_every_card_mercury_to_neptune(client):
    rows = _shelf(client, "/?sort=year")
    assert [badge for _, badge in rows] == [f"#{i} shortest year" for i in range(1, 9)]
    assert rows[0] == ("Mercury", "#1 shortest year")
    assert rows[-1] == ("Neptune", "#8 shortest year")


@pytest.mark.parametrize("url", ["/", "/?sort=sun", "/?sort=unknown"])
def test_sun_order_has_no_rank_badges(client, url):
    assert all(badge is None for _, badge in _shelf(client, url))
    assert not re.search(r"#\d", _visible_card_text(client, url))


def test_badge_sits_after_the_heading(client):
    html = client.get("/?sort=diameter").text
    assert re.search(r'<article class="planet-card"[^>]*>\s*<h3>[^<]*</h3>\s*<p class="rank">', html)


def test_badge_font_size_is_at_least_14px_at_every_width():
    css = (ROOT / "static" / "arcade.css").read_text()
    rules = re.findall(r"\.planet-card \.rank\s*\{([^}]*)\}", css)
    assert rules
    for rule in rules:
        size = re.search(r"font-size:\s*([\d.]+)rem", rule)
        assert size and float(size.group(1)) * 16 >= 14
