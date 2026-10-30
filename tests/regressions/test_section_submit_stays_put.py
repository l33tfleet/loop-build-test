"""#105: submitting a section's form keeps the URL hash and scroll position, and the result shows in that section.

Reuses the Node harness from test_controls_run_in_place.py, starting from a page whose URL carries the hash the
section nav sets (/#duel-title), so a submit that drops or swaps the hash is caught.
"""
import importlib.util
import json
import re
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlencode

import pytest

_spec = importlib.util.spec_from_file_location(
    "controls_run_in_place", Path(__file__).with_name("test_controls_run_in_place.py")
)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
BASE, SCRIPT, text = _base.BASE, _base.SCRIPT, _base.text

HASH = "#duel-title"
_LOCATION = 'location: { href: input.base + "/", origin: input.base,'
assert _LOCATION in _base.HARNESS
HARNESS = _base.HARNESS.replace(
    _LOCATION,
    'location: { href: input.base + "/" + input.query + input.hash, hash: input.hash, origin: input.base,',
    1,
)


def run(client, steps, responses, query=""):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is needed to run the home page script")
    payload = {
        "base": BASE,
        "hash": HASH,
        "query": query,
        "script": str(SCRIPT),
        "page": client.get("/" + query).text,
        "responses": {path: client.get(path).text for path in responses},
        "steps": steps,
    }
    out = subprocess.run(
        [node, "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, timeout=30, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def height_above(log, region):
    above = log["order"][: log["order"].index(region)]
    return sum((len(log["regions"][name]) + 5) // 10 for name in above)  # the harness's Math.round(length / 10)


def ratio(html):
    match = re.search(r'<p class="duel-ratio"[^>]*>(.*?)</p>', html, re.DOTALL)
    return text(match.group(1)).strip() if match else ""


# (form's region, fields, submitter, fetched path, region the result renders in, check on that region's HTML)
CASES = {
    "duel-compare": (
        "planet-duel", [["left", "jupiter"], ["right", "mercury"]], None, "/?left=jupiter&right=mercury",
        "planet-duel", lambda html: "Jupiter" in ratio(html) and "Mercury" in ratio(html),
    ),
    "quiz-choice": (
        "planet-quiz", [["round", "1"]], ["choice", "jupiter"], "/?round=1&choice=jupiter",
        "planet-quiz", lambda html: "Correct" in text(html),
    ),
    "birthday-age": (
        "birthday-booth", [["sort", "order"], ["age", "10"]], None, "/?sort=order&age=10",
        "birthday-booth", lambda html: "10" in text(html),
    ),
    "shelf-sort": (
        "shelf-sort", [["sort", "diameter"]], None, "/?sort=diameter",
        "planet-shelf", lambda html: "Largest diameter first" in text(html),
    ),
}


@pytest.mark.parametrize("case", list(CASES))
def test_section_submit_keeps_hash_scroll_and_section(client, case):
    region, fields, submitter, path, result_region, shows_result = CASES[case]
    start = run(client, [], [])
    home = start["regions"][result_region]
    step = {"do": "submit", "region": region, "fields": fields}
    if submitter:
        step["submitter"] = submitter
    log = run(client, [
        {"do": "scrollTo", "y": 600},
        {"do": "measure", "region": region, "as": "before"},
        step,
        {"do": "respond"},
        {"do": "measure", "region": region, "as": "after"},
    ], [path])
    assert log["prevented"] == [True]
    assert log["navigated"] == []
    assert log["fetched"] == [path]
    assert log["pushed"] == [BASE + path + HASH]
    # The page may scroll only by how much the sections above the tapped one grew, worked out here from their
    # HTML independently of the script (the harness sizes a region by its HTML length, so hidden inputs count).
    assert log["after"] == log["before"]
    assert log["scrollY"] == 600 + height_above(log, region) - height_above(start, region)
    if case != "shelf-sort":
        assert log["scrollY"] == 600, "nothing above this section changed, so the page must not scroll"
    assert log["regions"][result_region] != home
    assert shows_result(log["regions"][result_region])


# State for every section at once; each case's own fields then overwrite their part of it.
OTHERS = [["left", "saturn"], ["right", "mars"], ["round", "2"], ["age", "7"], ["sort", "diameter"]]


@pytest.mark.parametrize("case", list(CASES))
def test_section_submit_keeps_other_sections_state(client, case):
    region, fields, submitter, _, _, _ = CASES[case]
    submitted = fields + ([submitter] if submitter else [])
    names = [name for name, _ in submitted]
    kept = [pair for pair in OTHERS if pair[0] not in names]
    path = "/?" + urlencode([tuple(pair) for pair in kept + submitted])
    step = {"do": "submit", "region": region, "fields": fields}
    if submitter:
        step["submitter"] = submitter
    query = "?" + urlencode([tuple(pair) for pair in OTHERS])
    log = run(client, [{"do": "scrollTo", "y": 600}, step, {"do": "respond"}], [path], query=query)
    assert log["prevented"] == [True]
    assert log["navigated"] == []
    assert log["fetched"] == [path]
    assert log["pushed"] == [BASE + path + HASH]
    assert log["scrollY"] == 600


# Real Chromium, so layout and the browser's own scroll anchoring are real. Pages come from the app in-process
# (no server, no network). Each entry: (section the form sits in, steps a phone user takes, section the result
# shows in, text that result shows). Steps are (action, selector[, value]).
BROWSER_CASES = {
    "duel-compare": (
        ".planet-duel",
        [("click", "label[for=duel-left-jupiter]"), ("click", "label[for=duel-right-mercury]"),
         ("click", ".planet-duel button[type=submit]")],
        ".planet-duel", "times as wide as Mercury",
    ),
    "quiz-choice": (
        ".planet-quiz", [("click", ".planet-quiz button[name=choice]")], ".planet-quiz", "Your pick",
    ),
    "birthday-age": (
        ".birthday-booth", [("fill", "#earth-age", "10"), ("click", ".birthday-booth button[type=submit]")],
        ".birthday-booth", "years",
    ),
    "shelf-sort": (
        ".shelf-sort", [("select", "#planet-sort", "diameter"), ("click", ".shelf-sort button[type=submit]")],
        ".planet-shelf", "Largest diameter first",
    ),
}


def browse(client, check, grow_above=None):
    """Open /#duel-title on a 390px phone and hand the page to check(page).

    grow_above names a section whose in-place responses get 400px taller, so the tapped section below it has
    to be held in place against a real height change.
    """
    sync_api = pytest.importorskip("playwright.sync_api")

    def serve(route):
        response = client.get(route.request.url[len(BASE):])
        body = response.content
        if grow_above and route.request.resource_type == "fetch":
            needle = f'data-region="{grow_above}"'.encode()
            body = body.replace(needle, needle + b' style="padding-top: 400px"', 1)
        route.fulfill(status=response.status_code, body=body, content_type=response.headers.get("content-type"))

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 390, "height": 844})
            page.route("**/*", serve)
            page.goto(BASE + "/" + HASH)
            page.evaluate("window.stayedOnThisDocument = true")
            check(page)
        finally:
            browser.close()


def place(page, section):
    return page.evaluate(
        "s => [window.scrollY, document.querySelector(s).getBoundingClientRect().top, location.hash,"
        " window.stayedOnThisDocument === true]",
        section,
    )


@pytest.mark.parametrize("case", list(BROWSER_CASES))
def test_section_submit_stays_put_in_a_phone_browser(client, case):
    section, steps, result_section, result = BROWSER_CASES[case]

    def check(page):
        page.evaluate("s => window.scrollTo(0, document.querySelector(s).offsetTop - 100)", section)
        before = place(page, section)
        assert before[0] > 0, "the page did not scroll, so a jump to the top would go unnoticed"
        for action, selector, *value in steps:
            {"click": page.click, "fill": page.fill, "select": page.select_option}[action](selector, *value)
        page.wait_for_function("([s, t]) => document.querySelector(s).textContent.includes(t)",
                               arg=[result_section, result])
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(200)
        # Same document, same hash, same scroll position, same place on screen for the tapped section.
        assert place(page, section) == before

    browse(client, check)


def test_section_stays_put_in_a_phone_browser_when_a_section_above_grows(client):
    def check(page):
        page.evaluate("window.scrollTo(0, document.querySelector('.planet-quiz').offsetTop - 100)")
        duel_height = "document.querySelector('.planet-duel').offsetHeight"
        scroll_y, top, hash_, stayed = place(page, ".planet-quiz")
        height = page.evaluate(duel_height)
        page.click(".planet-quiz button[name=choice]")
        page.wait_for_selector(".planet-quiz button[disabled]")
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(200)
        grew = page.evaluate(duel_height) - height
        assert grew > 300
        # The quiz must not move on screen: the page scrolls by exactly what the duel grew, once, and no more.
        assert place(page, ".planet-quiz") == [scroll_y + grew, top, hash_, stayed]

    browse(client, check, grow_above="planet-duel")
