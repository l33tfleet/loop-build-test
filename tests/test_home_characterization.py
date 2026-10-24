"""Temporary home-page contract for the follow-up refactor; no app internals used."""

from html.parser import HTMLParser

import pytest


class Element:
    def __init__(self, tag, attrs=()):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []

    def find_all(self, tag=None, **attrs):
        found = []
        for child in self.children:
            if isinstance(child, Element):
                if (tag is None or child.tag == tag) and all(
                    child.attrs.get(key) == value for key, value in attrs.items()
                ):
                    found.append(child)
                found.extend(child.find_all(tag, **attrs))
        return found

    def one(self, tag=None, **attrs):
        found = self.find_all(tag, **attrs)
        assert len(found) == 1, (tag, attrs, len(found))
        return found[0]

    @property
    def raw_text(self):
        return "".join(
            child.raw_text if isinstance(child, Element) else child for child in self.children
        )

    @property
    def text(self):
        return " ".join(self.raw_text.split())


class PageParser(HTMLParser):
    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.root = Element("document")
        self.stack = [self.root]
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        node = Element(tag, attrs)
        self.stack[-1].children.append(node)
        if tag not in {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
                       "meta", "param", "source", "track", "wbr"}:
            self.stack.append(node)

    def handle_endtag(self, tag):
        assert self.stack[-1].tag == tag
        self.stack.pop()

    def handle_data(self, data):
        self.stack[-1].children.append(data)


# Literal expectations deliberately pin today's display, independently of app data/helpers.
PLANETS = [
    ("Mercury", "1st", "4,879", "0.38"),
    ("Venus", "2nd", "12,104", "0.95"),
    ("Earth", "3rd", "12,756", "1"),
    ("Mars", "4th", "6,792", "0.53"),
    ("Jupiter", "5th", "142,984", "11"),
    ("Saturn", "6th", "120,536", "9.4"),
    ("Uranus", "7th", "51,118", "4.0"),
    ("Neptune", "8th", "49,528", "3.9"),
]
SUN_ORDER = [p[0] for p in PLANETS]
DIAMETER_ORDER = ["Jupiter", "Saturn", "Uranus", "Neptune", "Earth", "Venus", "Mars", "Mercury"]
CASES = [
    pytest.param({}, id="none"),
    pytest.param({"age": "10"}, id="age"),
    pytest.param({"sort": "diameter"}, id="sort-diameter"),
    pytest.param({"sort": "year"}, id="sort-year"),
    pytest.param({"age": "10", "sort": "diameter"}, id="age-and-sort"),
    pytest.param({"left": "mercury", "right": "mars"}, id="duel-picks"),
    pytest.param({"age": "nan", "sort": "unknown", "left": "pluto", "right": "sun",
                  "round": "4"}, id="invalid"),
]


@pytest.fixture(params=CASES)
def home(client, request):
    params = request.param
    response = client.get("/", params=params)
    assert response.status_code == (422 if "round" in params else 200)
    return PageParser(response.text).root, params


def section(page, name):
    return page.one("section", **{"class": name})


def assert_get_form(form):
    assert form.attrs["action"] == "/"
    assert form.attrs["method"] == "get"


def test_home_header(home):
    page, _ = home
    header = page.one("header")
    assert header.one("h1").text == "Solar Arcade"
    assert header.one("p").text == (
        "Duel two planets by size, take the diameter quiz, find your planet birthdays, "
        "then see all eight on one scale or as a bar graph."
    )


def test_home_duel(home):
    page, params = home
    duel = section(page, "planet-duel")
    assert duel.one("h2").text == "Planet size duel"
    form = duel.one("form")
    assert_get_form(form)
    assert [node.text for node in form.find_all("legend")] == ["First planet", "Second planet"]
    assert form.one("button").text == "Compare"
    invalid = params.get("left") == "pluto"
    for side, default in (("left", "jupiter"), ("right", "earth")):
        radios = form.find_all("input", name=side)
        assert [node.attrs["value"] for node in radios] == [name.lower() for name in SUN_ORDER]
        assert [node.attrs["value"] for node in radios if "checked" in node.attrs] == [
            default if invalid else params.get(side, default)
        ]
        for radio, name in zip(radios, SUN_ORDER):
            assert form.one("label", **{"for": radio.attrs["id"]}).text == name
    if invalid:
        assert duel.one("p", role="alert").text == (
            "Choose two planets from the lists: unknown planet name."
        )
        assert not duel.find_all("figure")
        assert not duel.find_all("p", **{"class": "duel-ratio"})
    else:
        picked = "left" in params
        assert [node.text for node in duel.find_all("figcaption")] == (
            ["Mercury 4,879 km", "Mars 6,792 km"] if picked
            else ["Jupiter 142,984 km", "Earth 12,756 km"]
        )
        assert duel.one("p", **{"class": "duel-ratio"}).text == (
            "Mercury's diameter is 0.7 times Mars's." if picked
            else "Jupiter's diameter is 11.2 times Earth's."
        )
        assert not duel.find_all(role="alert")


def test_home_quiz(home):
    page, params = home
    quiz = section(page, "planet-quiz")
    assert quiz.one("h2").text == "Planet diameter quiz"
    if "round" in params:
        assert quiz.one("p", role="alert").text == "Choose a round from 1 through 3."
        link = quiz.one("a")
        assert link.text == "Start at round 1"
        assert link.attrs["href"] == "/?round=1"
        assert not quiz.find_all("form")
    else:
        assert quiz.one("p", **{"class": "quiz-round"}).text == "Round 1 of 3"
        form = quiz.one("form")
        assert_get_form(form)
        assert form.one("input", name="round").attrs == {
            "type": "hidden", "name": "round", "value": "1",
        }
        assert form.one("legend").text == "Which planet has the larger diameter?"
        assert [(b.text, b.attrs["name"], b.attrs["value"]) for b in form.find_all("button")] == [
            ("Jupiter", "choice", "jupiter"), ("Earth", "choice", "earth"),
        ]
        assert not quiz.find_all(role="status")
        assert not quiz.find_all("a")


def test_home_birthdays(home):
    page, params = home
    booth = section(page, "birthday-booth")
    assert booth.one("h2").text == "Planet birthdays"
    assert booth.one("p", id="birthday-note").text == (
        "How many trips around the Sun? A toy year conversion, not a calendar-date calculation."
    )
    form = booth.one("form")
    assert_get_form(form)
    assert form.one("label", **{"for": "earth-age"}).text == "Earth age (years)"
    age = form.one("input", name="age")
    for key, value in {"value": params.get("age", ""), "type": "number", "min": "0",
                       "max": "120", "step": "any"}.items():
        assert age.attrs[key] == value
    assert "required" in age.attrs
    expected_sort = params.get("sort", "sun")
    if expected_sort == "unknown":
        expected_sort = "sun"
    assert form.one("input", name="sort").attrs["value"] == expected_sort
    assert form.one("button").text == "Find my planet ages"
    assert form.one("a").text == "or try age 10"
    assert form.one("a").attrs["href"] == "/?age=10"
    results = booth.find_all("li", **{"class": "birthday-result"})
    if params.get("age") == "10":
        assert [node.text for node in results] == [
            "Mercury 41.5 years", "Venus 16.3 years", "Earth 10.0 years", "Mars 5.3 years",
            "Jupiter 0.8 years", "Saturn 0.3 years", "Uranus 0.1 years", "Neptune 0.1 years",
        ]
    else:
        assert not results
    if params.get("age") == "nan":
        assert booth.one("p", role="alert").text == "Enter a finite Earth age from 0 through 120."
        assert age.attrs["aria-invalid"] == "true"
        assert age.attrs["aria-describedby"] == "birthday-note age-error"
    else:
        assert not booth.find_all(role="alert")
        assert "aria-invalid" not in age.attrs
        assert age.attrs["aria-describedby"] == "birthday-note"


def test_home_diameter_scale(home):
    page, _ = home
    scale = section(page, "diameter-scale")
    assert scale.one("h2").text == "Diameter scale"
    assert scale.one("p", **{"data-view": "circles"}).text == (
        "Each circle's diameter is the planet's diameter divided by Jupiter's 142,984 km, "
        "on one linear scale. The circles overlap on a shared baseline so sizes compare directly."
    )
    assert scale.one("p", **{"data-view": "bars"}).text == (
        "Each bar's length is the planet's diameter divided by Jupiter's 142,984 km, "
        "on one linear scale. The bars share a left edge so sizes compare directly."
    )
    assert scale.one("legend").text == "View as"
    assert [node.text for node in scale.find_all("label")] == ["Overlapping circles", "Bar graph"]
    radios = scale.find_all("input", name="scale-view")
    assert [node.attrs["value"] for node in radios] == ["circles", "bars"]
    assert [node.attrs["value"] for node in radios if "checked" in node.attrs] == ["circles"]
    assert [node.text for node in scale.find_all("li")] == [
        f"{name} {diameter} km" for name, _, diameter, _ in PLANETS
    ]


def test_home_rocky_inset(home):
    page, _ = home
    inset = section(page, "rocky-inset")
    assert inset.one("h3").text == "Rocky planets, zoomed in"
    assert inset.one("p").text == (
        "Different scale from the chart above: here each circle's diameter is the planet's diameter "
        "divided by Earth's 12,756 km, so Earth fills the panel width."
    )
    assert [node.text for node in inset.find_all("li")] == [
        f"{name} {diameter} km" for name, _, diameter, _ in PLANETS[:4]
    ]


def test_home_shelf(home):
    page, params = home
    form = page.one("form", **{"class": "shelf-sort"})
    assert_get_form(form)
    assert form.one("label").text == "Planet shelf order"
    assert form.one("label").attrs["for"] == "planet-sort"
    select = form.one("select", name="sort")
    assert select.attrs["id"] == "planet-sort"
    options = select.find_all("option")
    assert [(node.attrs["value"], node.text) for node in options] == [
        ("sun", "Sun order"), ("diameter", "Largest diameter first"), ("year", "Shortest year first"),
    ]
    sort = params.get("sort", "sun")
    if sort == "unknown":
        sort = "sun"
    assert [node.attrs["value"] for node in options if "selected" in node.attrs] == [sort]
    assert form.one("button").text == "Apply order"
    if "age" in params:
        assert form.one("input", name="age").attrs["value"] == params["age"]
        assert form.one("input", name="age").attrs["type"] == "hidden"
    else:
        assert not form.find_all("input", name="age")
    shelf = section(page, "planet-shelf")
    assert shelf.one("h2", id="shelf-title").text == "The eight planets"
    assert shelf.one("p", **{"class": "shelf-note"}).text == {
        "sun": "In order from the Sun", "diameter": "Largest diameter first", "year": "Shortest year first",
    }[sort]
    cards = shelf.find_all("article")
    assert [card.one("h2").text for card in cards] == (
        DIAMETER_ORDER if sort == "diameter" else SUN_ORDER
    )
    by_name = {card.one("h2").text: card for card in cards}
    for name, ordinal, diameter, earths in PLANETS:
        card = by_name[name]
        assert card.one("p", **{"class": "order"}).text == f"{ordinal} from the Sun"
        assert card.one("p", **{"class": "label"}).text == "Diameter"
        assert card.one("p", **{"class": "diameter"}).text == f"{diameter} km"
        unit = "Earth" if earths == "1" else "Earths"
        assert card.one("p", **{"class": "earths"}).text == f"About {earths} {unit} wide"


def test_home_source(home):
    page, _ = home
    source = page.one("p", **{"class": "source"})
    assert source.text == (
        "Data: NASA Planetary Fact Sheet (equatorial diameter), snapshot 2026-10-24."
    )
    assert source.one("a").attrs["href"] == "https://nssdc.gsfc.nasa.gov/planetary/factsheet/"
