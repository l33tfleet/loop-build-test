import re
from html.parser import HTMLParser

import pytest

from app import main


class Controls(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.tags = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def shelf_names(html):
    return re.findall(r'<article class="planet-card"[^>]*>\s*<h2>(.*?)</h2>', html)


@pytest.mark.parametrize("sort,expected", [
    ("sun", ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]),
    ("diameter", ["Jupiter", "Saturn", "Uranus", "Neptune", "Earth", "Venus", "Mars", "Mercury"]),
    ("year", ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]),
    ("unknown", ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]),
    ("", ["Mercury", "Venus", "Earth", "Mars", "Jupiter", "Saturn", "Uranus", "Neptune"]),
])
def test_sort_order_and_active_choice_survive_reload(client, sort, expected):
    for _ in range(2):
        response = client.get("/", params={"sort": sort, "age": "30"})
        assert response.status_code == 200
        assert shelf_names(response.text) == expected
        tags = Controls(response.text).tags
        selected = [attrs["value"] for tag, attrs in tags if tag == "option" and "selected" in attrs]
        assert selected == [sort if sort in {"sun", "diameter", "year"} else "sun"]


@pytest.mark.parametrize("sort,field", [("sun", "order"), ("diameter", "diameter_km"), ("year", None)])
def test_sort_uses_stored_values_and_slug_ties(client, monkeypatch, sort, field):
    planets = [dict(p) for p in reversed(main.SNAPSHOT["planets"])]
    # All values tie except Mercury; neither snapshot order nor Sun order resolves the tie.
    if field:
        for planet in planets:
            planet[field] = 10 if planet["name"] == "Mercury" else 20
    else:
        monkeypatch.setattr(main, "ORBITAL_PERIOD_DAYS", {
            p["name"]: 10 if p["name"] == "Mercury" else 20 for p in planets
        })
    monkeypatch.setattr(main, "SNAPSHOT", {**main.SNAPSHOT, "planets": planets})
    tied = sorted(p["name"] for p in planets if p["name"] != "Mercury")
    expected = tied + ["Mercury"] if sort == "diameter" else ["Mercury"] + tied
    assert shelf_names(client.get("/", params={"sort": sort}).text) == expected


@pytest.mark.parametrize("age", ["30", "0", "12.50", "invalid", None])
def test_sort_form_preserves_age_and_birthday_form_preserves_sort(client, age):
    params = {"sort": "diameter"}
    if age is not None:
        params["age"] = age
    html = client.get("/", params=params).text
    forms = re.findall(r"<form\b.*?</form>", html, re.DOTALL)
    sort_form = next(form for form in forms if 'name="sort"' in form and "<select" in form)
    tags = Controls(sort_form).tags
    assert any(tag == "form" and attrs.get("action") == "/" and attrs.get("method") == "get"
               for tag, attrs in tags)
    select = next(attrs for tag, attrs in tags if tag == "select" and attrs.get("name") == "sort")
    assert any(tag == "label" and attrs.get("for") == select["id"] for tag, attrs in tags)
    assert {attrs["value"] for tag, attrs in tags if tag == "option"} == {"sun", "diameter", "year"}
    assert any(tag == "button" and attrs.get("type") == "submit" for tag, attrs in tags)
    if age is not None:
        assert any(tag == "input" and attrs.get("name") == "age" and attrs.get("value") == age
                   for tag, attrs in tags)
    submitted = {attrs["name"]: attrs.get("value", "") for tag, attrs in tags
                 if tag == "input" and "name" in attrs}
    submitted["sort"] = "year"
    changed = client.get("/", params=submitted).text
    age_input = next(attrs for tag, attrs in Controls(changed).tags if attrs.get("id") == "earth-age")
    assert age_input["value"] == (age or "")
    birthday_form = next(form for form in forms if 'id="earth-age"' in form)
    assert any(tag == "input" and attrs.get("name") == "sort" and attrs.get("value") == "diameter"
               for tag, attrs in Controls(birthday_form).tags)
