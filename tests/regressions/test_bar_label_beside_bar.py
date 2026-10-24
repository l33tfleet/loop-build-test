import re

HAS = ".diameter-scale:has(#scale-view-bars:checked) .scale-rows"
REM = 16  # px, body font-size
LABEL_REM = 0.9  # bar-view .scale-label font-size
# Widest single label piece ("142,984 km"): 10 tabular glyphs at <= 0.6em each.
WIDEST_PIECE_PX = 10 * 0.6 * LABEL_REM * REM


def _bar_rules(css, part):
    """Declarations of rules whose selector list includes the bar-view selector for `part`."""
    target = f"{HAS} {part}".strip()
    out = []
    for selectors, body in re.findall(r"([^{}]+)\{([^}]*)\}", css):
        selectors = re.sub(r"/\*.*?\*/", "", selectors, flags=re.DOTALL)
        if target in [s.strip() for s in selectors.split(",")]:
            out.append(body)
    return " ".join(out)


def _decl(rules, prop):
    found = re.findall(r"(?<![-\w])" + re.escape(prop) + r"\s*:\s*([^;]+);", rules)
    return found[-1].strip() if found else None


def test_label_column_comes_first_and_bar_follows(client):
    css = client.get("/static/arcade.css").text
    cols = _decl(_bar_rules(css, ".scale-row"), "grid-template-columns")
    assert cols, "bar rows need explicit columns"
    first, rest = re.match(r"(\S+)\s+(.+)", cols).groups()
    m = re.fullmatch(r"([\d.]+)rem", first)
    assert m, f"label column should be a fixed rem width, got {first!r}"
    assert float(m.group(1)) >= 9
    assert "1fr" in rest
    assert _decl(_bar_rules(css, ".scale-label"), "grid-column") == "1"
    assert _decl(_bar_rules(css, ".scale-track"), "grid-column") == "2"
    # Both live in row 1, so the label (after the track in the DOM) lands left of its bar.
    assert _decl(_bar_rules(css, ".scale-label"), "grid-row") == "1"
    assert _decl(_bar_rules(css, ".scale-track"), "grid-row") == "1"


def test_label_hugs_bar_and_wraps_instead_of_spilling(client):
    css = client.get("/static/arcade.css").text
    label = _bar_rules(css, ".scale-label")
    assert _decl(label, "justify-content") == "flex-end"
    assert _decl(label, "flex-wrap") == "wrap"
    assert _decl(label, "min-width") == "0"
    cols = _decl(_bar_rules(css, ".scale-row"), "grid-template-columns")
    width_px = float(re.match(r"([\d.]+)rem", cols).group(1)) * REM
    assert WIDEST_PIECE_PX < width_px


def test_circles_view_rules_untouched(client):
    css = client.get("/static/arcade.css").text
    base = " ".join(re.findall(r"(?:^|(?<=[}/]))\s*\.scale-(?:label|track|row)\s*\{([^}]*)\}", css, re.MULTILINE))
    assert "grid-column" not in base and "grid-row" not in base and "flex-wrap" not in base
