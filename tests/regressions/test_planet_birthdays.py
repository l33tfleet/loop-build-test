import re

import pytest

from app import main

PERIODS = {
    "Mercury": 88.0, "Venus": 224.7, "Earth": 365.2, "Mars": 687.0,
    "Jupiter": 4331.0, "Saturn": 10747.0, "Uranus": 30589.0, "Neptune": 59800.0,
}


def birthday_results(html):
    return re.findall(
        r'<li class="birthday-result"[^>]*>\s*<span>([^<]+)</span>\s*'
        r'<strong>([0-9]+\.[0-9])</strong>\s*<span>years</span>\s*</li>', html,
    )


def test_birthday_booth_has_labeled_ordinary_get_form(client):
    html = client.get("/").text
    assert "Planet birthdays" in html
    assert re.search(r'<form\b[^>]*action="/"[^>]*method="get"', html)
    assert '<label for="earth-age">Earth age (years)</label>' in html
    field = re.search(r'<input\b[^>]*id="earth-age"[^>]*>', html).group()
    for attribute in ('name="age"', 'min="0"', 'max="120"', 'step="any"'):
        assert attribute in field
    assert 'type="submit"' in html
    assert "not a calendar-date calculation" in html
    assert birthday_results(html) == []


@pytest.mark.parametrize("age", [0, 0.1, 0.95, 30, 30.26, 119.99, 120])
def test_planet_birthdays_use_period_ratio_and_one_decimal(client, age):
    response = client.get("/", params={"age": str(age)})
    assert response.status_code == 200
    assert birthday_results(response.text) == [
        (name, f"{age if name == 'Earth' else age * PERIODS['Earth'] / period:.1f}")
        for name, period in PERIODS.items()
    ]
    assert dict(birthday_results(response.text))["Earth"] == f"{age:.1f}"
    assert 'role="alert"' not in response.text


@pytest.mark.parametrize("age", ["-0", "-0.0"])
def test_signed_zero_displays_as_zero(client, age):
    results = birthday_results(client.get("/", params={"age": age}).text)
    assert results == [(name, "0.0") for name in PERIODS]


def test_birthdays_read_stored_orbital_periods(client, monkeypatch):
    monkeypatch.setitem(main.ORBITAL_PERIOD_DAYS, "Earth", 400.0)
    monkeypatch.setitem(main.ORBITAL_PERIOD_DAYS, "Mars", 800.0)
    results = dict(birthday_results(client.get("/", params={"age": "30"}).text))
    assert results["Earth"] == "30.0"
    assert results["Mars"] == "15.0"


@pytest.mark.parametrize("age", [
    "", " ", "hello", "<script>alert(1)</script>", "-0.01", "120.01",
    "nan", "NaN", "inf", "-inf", "Infinity", "1e999", "-1e999",
])
def test_invalid_age_explains_problem_without_results(client, age):
    response = client.get("/", params={"age": age})
    assert response.status_code == 200
    assert 'role="alert"' in response.text
    assert "Enter a finite Earth age from 0 through 120." in response.text
    assert birthday_results(response.text) == []
    assert "Traceback" not in response.text
    assert "<script>" not in response.text
    assert 'data-marker="solar-arcade"' in response.text
