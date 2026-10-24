"""#77: tapping a 'View as' pill must not scroll the page, and the pills read like the duel pills."""
import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"
JS = Path(__file__).resolve().parents[2] / "static" / "arcade.js"
SECTION = re.compile(r'<section class="diameter-scale"[^>]*>(.*?)</section>', re.DOTALL)
FIELDSET = re.compile(r'<fieldset class="scale-views"[^>]*>(.*?)</fieldset>', re.DOTALL)
PILL = re.compile(r'<span class="scale-view-pill">\s*(<input[^>]*>)\s*(<label[^>]*>[^<]*</label>)\s*</span>')


def _rules(css, selector):
    pattern = r"(?:^|[},])\s*" + re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}"
    return " ".join(re.findall(pattern, css, re.MULTILINE))


def _px(value):
    number, unit = re.fullmatch(r"([\d.]+)(px|rem|em)", value).groups()
    return float(number) * (1 if unit == "px" else 16)


def test_each_radio_sits_inside_its_own_pill(client):
    group = FIELDSET.search(SECTION.search(client.get("/").text).group(1)).group(1)
    pills = PILL.findall(group)
    assert [re.search(r'id="([^"]+)"', radio).group(1) for radio, _ in pills] == [
        "scale-view-circles", "scale-view-bars"]
    for radio, label in pills:
        assert 'class="scale-view"' in radio and 'type="radio"' in radio
        assert re.search(r'for="([^"]+)"', label).group(1) == re.search(r'id="([^"]+)"', radio).group(1)
    # Nothing but the legend and the two pills sits in the group.
    rest = PILL.sub("", re.sub(r"<legend>[^<]*</legend>", "", group))
    assert rest.strip() == ""


def test_hidden_radio_is_anchored_over_its_pill():
    css = CSS.read_text()
    assert re.search(r"position:\s*relative", _rules(css, ".scale-views"))
    assert re.search(r"position:\s*relative", _rules(css, ".scale-view-pill"))
    radio = _rules(css, ".scale-view")
    assert re.search(r"position:\s*absolute", radio)
    assert re.search(r"inset:\s*0", radio)
    assert re.search(r"opacity:\s*0", radio)


def test_legend_and_labels_are_legible():
    css = CSS.read_text()
    for selector in (".scale-views legend", ".scale-view-label"):
        rule = _rules(css, selector)
        assert re.search(r"color:\s*var\(--ink\)", rule), selector
        size = re.search(r"font-size:\s*([\d.]+(?:px|rem|em))", rule)
        assert size and _px(size.group(1)) >= 16, selector
    # No phone override shrinks the pills back down.
    for block in re.findall(r"@media[^{]*\{((?:[^{}]*\{[^}]*\})*)\s*\}", css):
        for selector, body in re.findall(r"([^{}]+)\{([^}]*)\}", block):
            if "scale-view" in selector:
                size = re.search(r"font-size:\s*([\d.]+(?:px|rem|em))", body)
                assert not size or _px(size.group(1)) >= 16, selector


def test_pills_are_tall_enough_to_tap():
    min_height = re.search(r"min-height:\s*([\d.]+(?:px|rem))", _rules(CSS.read_text(), ".scale-view-label"))
    assert min_height and _px(min_height.group(1)) >= 44


def test_selected_pill_is_filled_and_checked():
    css = CSS.read_text()
    checked = _rules(css, ".scale-view:checked + .scale-view-label")
    fill = re.search(r"background:\s*([^;]+)", checked)
    assert fill and fill.group(1).strip() not in ("none", "transparent")
    mark = _rules(css, ".scale-view:checked + .scale-view-label::before")
    assert re.search(r'content:\s*"\\2713|content:\s*"✓', mark)


def test_pills_wrap_instead_of_overflowing():
    rule = _rules(CSS.read_text(), ".scale-views")
    assert re.search(r"display:\s*flex", rule)
    assert re.search(r"flex-wrap:\s*wrap", rule)


def test_focus_ring_and_no_script_switching_remain():
    css = CSS.read_text()
    assert re.search(r"outline:\s*\dpx solid", _rules(css, ".scale-view:focus-visible + .scale-view-label"))
    assert re.search(r"display:\s*grid", _rules(css, ".diameter-scale:has(#scale-view-bars:checked) .scale-rows"))
    # The script never drives the toggle on a tap; CSS alone switches the view.
    assert "scale-view-pill" not in JS.read_text()
