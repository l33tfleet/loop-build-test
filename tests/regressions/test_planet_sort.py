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
