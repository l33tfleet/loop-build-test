import re
from html import unescape

SUN_ORDER = ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]
EXPECTED_KM = {"Mercury": 4879, "Venus": 12104, "Earth": 12756, "Mars": 6792,
               "Jupiter": 142984, "Saturn": 120536, "Uranus": 51118, "Neptune": 49528}
SECTION = re.compile(r'<section class="diameter-scale"[^>]*>(.*?)</section>', re.DOTALL)
ROW = re.compile(r'<li class="scale-row"[^>]*>(.*?)</li>', re.DOTALL)


def _text(pattern, body):
    return unescape(re.sub(r"<[^>]+>", "", re.search(pattern, body, re.DOTALL).group(1))).strip()


def _rows(html):
    section = SECTION.search(html)
    assert section, "diameter scale section missing"
    rows = []
    for body in ROW.findall(section.group(1)):
        name = _text(r'class="scale-name"[^>]*>(.*?)</', body)
        value = _text(r'class="scale-value"[^>]*>(.*?)</', body)
        width = float(re.search(r'class="scale-bar"[^>]*style="width:\s*([\d.]+)%', body).group(1))
        rows.append((name, value, width))
    return rows


def test_scale_is_labeled_and_above_shelf(client):
    html = client.get("/").text
    section = SECTION.search(html)
    assert section
    assert re.search(r"<h2[^>]*>[^<]*[Dd]iameter", section.group(1))
    assert section.start() < html.index('class="shelf"')


def test_eight_rows_in_sun_order_with_values_and_units(client):
    rows = _rows(client.get("/").text)
    assert [name for name, _, _ in rows] == SUN_ORDER
    for name, value, _ in rows:
        assert value == f"{EXPECTED_KM[name]:,} km"


def test_bar_widths_are_diameter_over_largest(client):
    widths = {name: width for name, _, width in _rows(client.get("/").text)}
    largest = max(EXPECTED_KM.values())
    for name, km in EXPECTED_KM.items():
        assert abs(widths[name] - 100 * km / largest) < 0.01, name
    assert widths["Jupiter"] == 100
    assert abs(widths["Mercury"] - 3.4123) < 0.001


def test_no_minimum_width_or_log_distortion(client):
    css = client.get("/static/arcade.css").text
    bar_rules = re.findall(r"\.scale-bar[^{]*\{([^}]*)\}", css)
    assert bar_rules
    for rule in bar_rules:
        assert "min-width" not in rule
        assert not re.search(r"(?<!-)width\s*:", rule)
    html = SECTION.search(client.get("/").text).group(1)
    assert "log" not in html.lower()
