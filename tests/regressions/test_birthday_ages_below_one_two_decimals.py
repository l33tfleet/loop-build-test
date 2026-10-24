import re

import pytest

from app import main

PERIODS = {
    "Mercury": 88.0, "Venus": 224.7, "Earth": 365.2, "Mars": 687.0,
    "Jupiter": 4331.0, "Saturn": 10747.0, "Uranus": 30589.0, "Neptune": 59800.0,
}
RESULT = re.compile(
    r'<li class="birthday-result"[^>]*>\s*<span>([^<]+)</span>\s*'
    r'<strong>([0-9]+\.[0-9]{1,2})</strong>\s*<span>years</span>\s*</li>'
)


def results(client, age):
    response = client.get("/", params={"age": str(age)})
    assert response.status_code == 200
    assert 'role="alert"' not in response.text
    return RESULT.findall(response.text)


def expected(years):
    return f"{years:.2f}" if 0 < round(years, 2) < 1 else f"{years:.1f}"


def test_age_twelve_keeps_uranus_and_neptune_apart(client):
    shown = dict(results(client, 12))
    assert shown["Uranus"] == "0.14"
    assert shown["Neptune"] == "0.07"
    assert shown["Mercury"] == "49.8"
    assert shown["Earth"] == "12.0"


@pytest.mark.parametrize("age", ["0", "0.0", "-0"])
def test_age_zero_still_reads_zero_point_zero_everywhere(client, age):
    assert results(client, age) == [(name, "0.0") for name in PERIODS]


@pytest.mark.parametrize("age", [0.1, 0.5, 0.95, 0.999, 10, 12, 30, 30.26, 119.99, 120])
def test_every_planet_uses_two_decimals_below_one_and_one_otherwise(client, age):
    assert results(client, age) == [
        (name, expected(age if name == "Earth" else age * PERIODS["Earth"] / period))
        for name, period in PERIODS.items()
    ]


def test_value_rounding_up_to_one_reads_one_point_zero(client):
    # Earth 0.999 rounds to 1.00 at two decimals, so it is shown as an age of one.
    assert dict(results(client, 0.999))["Earth"] == "1.0"


def test_formatting_follows_stored_orbital_periods(client, monkeypatch):
    monkeypatch.setitem(main.ORBITAL_PERIOD_DAYS, "Neptune", 365.2 * 30)
    assert dict(results(client, 1))["Neptune"] == "0.03"


def test_try_age_ten_link_shows_eight_results_with_ten_prefilled(client):
    html = client.get("/").text
    link = re.search(r'<a\b[^>]*class="birthday-try"[^>]*>', html).group()
    href = re.search(r'href="([^"]+)"', link).group(1)
    response = client.get(href)
    assert response.status_code == 200
    shown = RESULT.findall(response.text)
    assert len(shown) == 8
    assert ("Earth", "10.0") in shown
    assert ("Uranus", "0.12") in shown
    assert ("Neptune", "0.06") in shown
    field = re.search(r'<input\b[^>]*id="earth-age"[^>]*>', response.text).group()
    assert re.search(r'value="10(\.0)?"', field)
