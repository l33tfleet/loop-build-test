import itertools
import re
from html import unescape

ROCKY_KM = {"Mercury": 4879, "Venus": 12104, "Earth": 12756, "Mars": 6792}
INSET = re.compile(r'<section class="rocky-inset"[^>]*>(.*?)</section>', re.DOTALL)
ROW = re.compile(r'<li class="inset-row"([^>]*)>(.*?)</li>', re.DOTALL)
REM = 16  # px, body font-size
LINE_HEIGHT = 1.2
LABEL_REM = 0.8
# 390px phone: minus body padding (2 x 16px) and the panel's padding + border (2 x 17px).
PHONE_FRAME = 390 - 32 - 34


def _text(pattern, body):
    return unescape(re.sub(r"<[^>]+>", "", re.search(pattern, body, re.DOTALL).group(1))).strip()


def _rules(css, selector):
    return " ".join(re.findall(re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", css))


def _inset(client):
    html = client.get("/").text
    match = INSET.search(html)
    assert match, "rocky planet inset missing"
    return html, match


def _rows(client):
    rows = {}
    for attrs, body in ROW.findall(_inset(client)[1].group(1)):
        name = _text(r'class="inset-name"[^>]*>(.*?)</', body)
        value = _text(r'class="inset-value"[^>]*>(.*?)</', body)
        width = float(re.search(r'class="inset-circle"[^>]*style="width:\s*([\d.]+)%', body).group(1))
        mode, y = re.search(r'class="inset-label inset-label--(\w+)"[^>]*style="--y:\s*([\d.]+)%', body).groups()
        rows[name] = {"value": value, "width": width, "mode": mode, "y": float(y), "attrs": attrs}
    return rows


def test_inset_sits_under_the_circle_chart_and_above_the_shelf(client):
    html, match = _inset(client)
    assert html.index('class="diameter-scale"') < match.start() < html.index('class="shelf"')
    title = _text(r"<h3[^>]*>(.*?)</h3>", match.group(1))
    assert title == "Rocky planets, zoomed in"


def test_inset_shows_the_four_rocky_planets_scaled_to_earth(client):
    rows = _rows(client)
    assert list(rows) == ["Mercury", "Venus", "Earth", "Mars"]
    for name, km in ROCKY_KM.items():
        assert rows[name]["value"] == f"{km:,} km"
        assert abs(rows[name]["width"] - 100 * km / ROCKY_KM["Earth"]) < 0.01, name
    assert rows["Earth"]["width"] == 100
    assert 94 < rows["Venus"]["width"] < 96 and 53 < rows["Mars"]["width"] < 54


def test_caption_states_the_different_earth_based_scale(client):
    body = _inset(client)[1].group(1)
    note = _text(r'class="inset-note"[^>]*>(.*?)</p>', body).lower()
    assert "different scale" in note
    assert "earth" in note and "12,756 km" in note
    assert "chart above" in note


def test_inset_circles_share_one_baseline_like_the_main_chart(client):
    css = client.get("/static/arcade.css").text
    frame = _rules(css, ".inset-rows")
    assert re.search(r"aspect-ratio:\s*1\b", frame) and re.search(r"position:\s*relative", frame)
    track = _rules(css, ".inset-track")
    assert re.search(r"position:\s*absolute", track) and re.search(r"inset:\s*0", track)
    assert re.search(r"align-items:\s*flex-end", track)
    circle = _rules(css, ".inset-circle")
    assert re.search(r"border-radius:\s*50%", circle) and re.search(r"aspect-ratio:\s*1\b", circle)
    z = {name: int(re.search(r"--z:\s*(\d+)", row["attrs"]).group(1)) for name, row in _rows(client).items()}
    assert [z[n] for n in sorted(ROCKY_KM, key=ROCKY_KM.get, reverse=True)] == sorted(z.values())


def test_labels_do_not_overlap_at_390px(client):
    rows = _rows(client)
    label_pct = 2 * LINE_HEIGHT * LABEL_REM * REM / PHONE_FRAME * 100  # name + value lines
    spans = []
    for name, row in rows.items():
        if row["mode"] == "inside":
            top = 100 - row["y"] + 4  # .inset-label--inside: top = 100% - y + 4%
        else:
            assert row["mode"] == "above", name
            top = 100 - row["y"] - 1 - label_pct  # bottom = y + 1%
        spans.append((top, top + label_pct, name))
    spans.sort()
    for (_, end, a), (start, _, b) in itertools.pairwise(spans):
        assert end <= start, f"{a} label overlaps {b}"
    css = client.get("/static/arcade.css").text
    assert re.search(r"font-size:\s*0\.8rem", _rules(css, ".inset-label"))


def test_inset_hides_in_bar_view(client):
    css = client.get("/static/arcade.css").text
    assert re.search(r"display:\s*none", _rules(css, "main:has(#scale-view-bars:checked) .rocky-inset"))
