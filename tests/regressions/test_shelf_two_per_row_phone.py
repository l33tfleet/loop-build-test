import re
from html import unescape

BODY_PAD = 16  # px each side, body padding
MAIN_MAX = 960  # px, header/main/shelf max-width
REM = 16
BORDER = 1  # px, .planet-card border
CARD = re.compile(r'<article class="planet-card"[^>]*>(.*?)</article>', re.DOTALL)
# Helvetica/Arial advance widths in 1/1000 em; system-ui faces run a little wider, so FUDGE adds headroom.
WIDTHS = dict(zip("abcdefghijklmnopqrstuvwxyz",
                  [556, 556, 500, 556, 556, 278, 556, 556, 222, 222, 500, 222, 833,
                   556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500]))
WIDTHS |= dict(zip("ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                   [667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833,
                    722, 778, 667, 778, 722, 667, 611, 722, 667, 944, 667, 667, 611]))
WIDTHS |= {d: 556 for d in "0123456789"} | {" ": 278, ",": 278, ".": 278, "-": 333}
FUDGE = 1.08
BOLD_FUDGE = 1.15  # h2 is bold
# (selector inside the card, class or tag in the markup, uppercase?)
LINES = [("h2", r"<h2[^>]*>(.*?)</h2>", False), (".order", r'class="order"[^>]*>(.*?)<', False),
         (".label", r'class="label"[^>]*>(.*?)<', True), (".diameter", r'class="diameter"[^>]*>(.*?)<', False),
         (".earths", r'class="earths"[^>]*>(.*?)<', False)]


def _blocks(css, viewport):
    """Top-level rule bodies plus the bodies of every max-width media query that matches the viewport."""
    out = re.sub(r"@media[^{]*\{(?:[^{}]*\{[^}]*\})*\s*\}", "", css)
    for width, body in re.findall(r"@media\s*\(max-width:\s*(\d+)px\)\s*\{((?:[^{}]*\{[^}]*\})*)\s*\}", css):
        if viewport <= int(width):
            out += "\n" + body
    return out


def _decl(css, viewport, selector, prop):
    """Last value of prop across all rules for exactly this selector (cascade order, equal specificity)."""
    sel = re.escape(selector)
    bodies = re.findall(r"(?:^|(?<=[}/]))\s*" + sel + r"\s*\{([^}]*)\}", _blocks(css, viewport), re.MULTILINE)
    values = [v.strip() for b in bodies for v in re.findall(r"(?<![-\w])" + re.escape(prop) + r":\s*([^;]+);", b)]
    return values[-1] if values else None


def _px(value):
    if value.endswith("rem"):
        return float(value[:-3]) * REM
    assert value.endswith("px"), value
    return float(value[:-2])


def _columns(css, viewport):
    content = min(viewport - 2 * BODY_PAD, MAIN_MAX)
    template = _decl(css, viewport, ".shelf", "grid-template-columns")
    col_min = min(content, float(re.search(r"minmax\(min\(100%,\s*([\d.]+)px\)", template).group(1)))
    gap = _px(_decl(css, viewport, ".shelf", "gap"))
    cols = max(1, int((content + gap) // (col_min + gap)))
    return cols, (content - gap * (cols - 1)) / cols


def _text_px(text, font_px, letter_spacing_em=0.0):
    return sum(WIDTHS.get(c, 1000) for c in text) / 1000 * font_px + letter_spacing_em * font_px * len(text)


def _card_lines(client):
    for body in CARD.findall(client.get("/").text):
        for selector, pattern, upper in LINES:
            text = " ".join(unescape(re.search(pattern, body, re.DOTALL).group(1)).split())
            yield selector, text.upper() if upper else text


def test_phone_390_shows_two_cards_per_row(client):
    css = client.get("/static/arcade.css").text
    assert _columns(css, 390)[0] == 2


def test_desktop_960_keeps_four_balanced_columns(client):
    css = client.get("/static/arcade.css").text
    cols, width = _columns(css, 960 + 2 * BODY_PAD)
    assert cols == 4 and width >= 200


