import re

import pytest

DIAMETERS = {
    "mercury": 4879, "venus": 12104, "earth": 12756, "mars": 6792,
    "jupiter": 142984, "saturn": 120536, "uranus": 51118, "neptune": 49528,
}


def duel(html):
    match = re.search(r'<section class="planet-duel"[^>]*>(.*?)</section>', html, re.DOTALL)
    assert match, "duel panel missing"
    return match.group(1)


def sentence(section):
    match = re.search(r'<p class="duel-ratio"[^>]*>(.*?)</p>', section, re.DOTALL)
    return " ".join(re.sub(r"<[^>]+>", "", match.group(1)).split()) if match else None


def radios(section, name):
    return re.findall(rf'<input type="radio" id="([\w-]+)" name="{name}" value="(\w+)"( checked)?>', section)


def selected(section, name):
    return [value for _, value, checked in radios(section, name) if checked]


def test_duel_is_first_panel_with_labeled_selectors_and_get_form(client):
    html = client.get("/").text
    main = html.split("<main>", 1)[1]
    assert main.lstrip().startswith('<section class="planet-duel"')
    section = duel(html)
    assert re.search(r'<form\b[^>]*action="/"[^>]*method="get"', section)
    groups = re.findall(r'<fieldset\b[^>]*>\s*<legend>([^<]+)</legend>(.*?)</fieldset>', section, re.DOTALL)
    assert [legend for legend, _ in groups] == ["First planet", "Second planet"]
    for (_, group), name in zip(groups, ("left", "right")):
        found = radios(group, name)
        assert [value for _, value, _ in found] == list(DIAMETERS)
        for radio_id, value, _ in found:
            assert f'<label for="{radio_id}">{value.title()}</label>' in group
    assert re.search(r'<button type="submit"', section)
    assert "tabindex" not in section


@pytest.mark.parametrize("params", [
    {"left": "pluto"}, {"right": "sun"}, {"left": "", "right": "earth"}, {"left": "Jupiter"},
    {"left": "<script>alert(1)</script>", "right": "earth"},
])
def test_unknown_slug_returns_clear_validation_response(client, params):
    response = client.get("/", params=params)
    assert response.status_code == 422
    section = duel(response.text)
    assert 'role="alert"' in section
    assert "Choose two planets from the lists" in section
    assert sentence(section) is None
    assert "<script>" not in response.text
    assert 'data-marker="solar-arcade"' in response.text


def test_healthz_and_convert_still_work(client):
    assert client.get("/healthz").json() == {"ok": True}
    assert client.get("/convert", params={"value": 1, "src": "km", "dst": "mi"}).status_code == 200
