import re
from pathlib import Path

CSS = Path(__file__).resolve().parents[2] / "static" / "arcade.css"
SECTION = re.compile(r'<section class="diameter-scale"[^>]*>(.*?)</section>', re.DOTALL)
FIELDSET = re.compile(r'<fieldset class="scale-views"[^>]*>(.*?)</fieldset>', re.DOTALL)


def _fieldset(client):
    section = SECTION.search(client.get("/").text).group(1)
    match = FIELDSET.search(section)
    assert match, "scale-view radios are not grouped in a fieldset"
    return section, match


def _rules(css, selector):
    return " ".join(re.findall(re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", css))


def test_radios_and_labels_sit_in_a_fieldset_named_view_as(client):
    section, match = _fieldset(client)
    group = match.group(1)
    legend = re.search(r"<legend[^>]*>\s*([^<]*?)\s*</legend>", group)
    assert legend and legend.group(1) == "View as"
    assert group.lstrip().startswith("<legend")
    for view in ("circles", "bars"):
        assert re.search(rf'<input[^>]*type="radio"[^>]*id="scale-view-{view}"', group)
        assert f'for="scale-view-{view}"' in group
    # Nothing else in the section is a scale-view radio, and the list stays outside the group.
    assert len(re.findall(r'name="scale-view"', section)) == 2
    assert "scale-rows" not in group
    assert match.end() <= section.index('class="scale-rows"')


def test_fieldset_is_borderless_and_pills_stay_on_one_row():
    css = CSS.read_text()
    fieldset = _rules(css, ".scale-views")
    assert re.search(r"border:\s*0", fieldset)
    assert re.search(r"white-space:\s*nowrap", fieldset)
    legend = _rules(css, ".scale-views legend")
    assert re.search(r"float:\s*left", legend), "legend must sit inline before the pills"


def test_bar_view_switches_through_has_since_radios_are_no_longer_siblings():
    css = CSS.read_text()
    has = ".diameter-scale:has(#scale-view-bars:checked) .scale-rows"
    assert re.search(r"display:\s*grid", _rules(css, has))
    assert re.search(r"display:\s*none", _rules(css, f"{has} .scale-leader"))
    assert re.search(r"position:\s*static", _rules(css, f"{has} .scale-track"))
    # The focus ring still follows keyboard focus onto the pill.
    assert re.search(r"outline:\s*2px", _rules(css, ".scale-view:focus-visible + .scale-view-label"))
