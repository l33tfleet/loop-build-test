"""#123: after an in-place swap, focus stays on the same control and one persistent status announces the result.

Node runs static/arcade.js against a small DOM built from the server's real HTML (elements, parents, text),
so these run offline in `make check`. The browser tests repeat the key checks in Chromium when Playwright is
installed.
"""
import importlib.util
import json
import re
import shutil
import subprocess
from hashlib import sha256
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "static" / "arcade.js"
BASE = "http://testserver"
VOID = {"input", "br", "img", "hr", "meta", "link", "source", "wbr"}

DUEL_FIELDS = [["left", "saturn"], ["right", "venus"]]
DUEL_URL = "/?left=saturn&right=venus"
SATURN_VENUS = "Saturn is 10.0 times as wide as Venus."
AGES_10 = ("Mercury 41.5 years, Venus 16.3 years, Earth 10.0 years, Mars 5.3 years, Jupiter 0.84 years, "
           "Saturn 0.34 years, Uranus 0.12 years, Neptune 0.06 years")


class Page(HTMLParser):
    """Flatten the page into elements with parent links, noting which data-region each one is in."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.nodes, self.stack = [], []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = {k: (v if v is not None else "") for k, v in attrs}
        parent = self.stack[-1] if self.stack else None
        region = attrs.get("data-region") or (self.nodes[parent]["region"] if parent is not None else None)
        self.nodes.append({"tag": tag, "attrs": attrs, "text": "", "parent": parent, "region": region})
        if tag not in VOID:
            self.stack.append(len(self.nodes) - 1)

    def handle_data(self, data):
        for index in self.stack:
            self.nodes[index]["text"] += data

    def handle_endtag(self, tag):
        while self.stack:
            if self.nodes[self.stack.pop()]["tag"] == tag:
                break


HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const listeners = {}, pending = [];
const body = {tagName: 'BODY', events: {}};

function matchOne(node, s) {
  const tag = /^[\w-]+/.exec(s);
  if (tag && tag[0].toUpperCase() !== node.tagName) return false;
  const id = /#([\w-]+)/.exec(s);
  if (id && id[1] !== node.id) return false;
  for (const c of s.matchAll(/\.([\w-]+)/g))
    if (!(node.attrs.class || '').split(/\s+/).includes(c[1])) return false;
  return [...s.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)].every(
    m => m[1] in node.attrs && (m[2] === undefined || node.attrs[m[1]] === m[2]));
}
class El {
  constructor(data) {
    this.tagName = data.tag.toUpperCase(); this.attrs = {...data.attrs}; this.text = data.text;
    this.events = {}; this.parent = null; this.children = [];
  }
  get id() { return this.attrs.id || ''; }
  get name() { return this.attrs.name || ''; }
  get value() { return this.attrs.value || ''; }
  get type() { return this.attrs.type || ''; }
  get textContent() { return this.text; }
  set textContent(v) { this.text = String(v); this.writes = (this.writes || []).concat([this.text]); }
  get outerHTML() { return JSON.stringify([this.attrs, this.text, this.children.map(c => c.outerHTML)]); }
  getAttribute(k) { return this.attrs[k] ?? null; }
  setAttribute(k, v) { this.attrs[k] = v; }
  removeAttribute(k) { delete this.attrs[k]; }
  addEventListener(t, fn) { (this.events[t] ||= []).push(fn); }
  matches(sel) { return sel.split(',').some(s => matchOne(this, s.trim())); }
  descendants() { return this.children.flatMap(c => [c, ...c.descendants()]); }
  querySelectorAll(sel) { return this.descendants().filter(n => n.matches(sel)); }
  querySelector(sel) { return this.querySelectorAll(sel)[0] || null; }
  closest(sel) { let n = this; while (n && !(n.matches && n.matches(sel))) n = n.parent; return n || null; }
  contains(n) { while (n) { if (n === this) return true; n = n.parent; } return false; }
  replaceWith(fresh) {
    const siblings = this.parent.children;
    if (this.contains(document.activeElement)) document.activeElement = body;
    siblings[siblings.indexOf(this)] = fresh; fresh.parent = this.parent; this.parent = null;
  }
  getBoundingClientRect() { return {top: 0, bottom: 10}; }
  focus(options) {
    if (!document.contains(this)) return;
    document.activeElement = this; this.focusOptions = options;
  }
}
function build(nodes) {
  const root = new El({tag: 'html', attrs: {}, text: ''});
  const els = nodes.map(n => new El(n));
  nodes.forEach((n, i) => { const p = n.parent === null ? root : els[n.parent]; els[i].parent = p; p.children.push(els[i]); });
  return {
    root,
    querySelector: sel => root.querySelector(sel),
    querySelectorAll: sel => root.querySelectorAll(sel),
    getElementById: id => root.querySelector('#' + id),
  };
}
let page = build(input.page);
const document = {
  activeElement: body,
  addEventListener(t, fn) { (listeners[t] ||= []).push(fn); },
  querySelector: s => page.querySelector(s),
  querySelectorAll: s => page.querySelectorAll(s),
  getElementById: id => page.getElementById(id),
  contains: n => page.root.contains(n),
  adoptNode: n => n,
};
const win = {
  scrollY: 0,
  location: {href: input.base + input.start, origin: input.base, hash: '',
    assign(url) { throw new Error('unexpected navigation: ' + url); }},
  scrollBy() {},
  addEventListener(t, fn) { (listeners['window:' + t] ||= []).push(fn); },
};
vm.runInNewContext(fs.readFileSync(input.script, 'utf8'), {
  document, window: win, URL, setTimeout, requestAnimationFrame: fn => setTimeout(fn, 0),
  CSS: {escape: s => String(s).replace(/["\\]/g, '\\$&')},
  history: {pushState(s, t, url) { win.location.href = url; }},
  FormData: class {
    constructor(form) { this.pairs = form.fields.map(p => p.slice()); }
    append(k, v) { this.pairs.push([k, v]); }
    [Symbol.iterator]() { return this.pairs[Symbol.iterator](); }
  },
  fetch: url => new Promise(resolve => pending.push(() => {
    const path = new URL(url).pathname + new URL(url).search;
    if (!(path in input.responses)) throw new Error('unexpected fetch: ' + path);
    resolve({text: async () => input.responses[path]});
  })),
  DOMParser: class { parseFromString(nodes) { return build(nodes); } },
});
const settle = () => new Promise(r => setTimeout(r, 20));
(async () => {
  const logs = [];
  const status = page.querySelector('[role="status"]#arcade-status');
  for (const step of input.steps) {
    const region = page.querySelector('[data-region="' + step.region + '"]');
    if (step.focus) region.querySelector(step.focus).focus({preventScroll: true});
    const form = {action: input.base + '/', method: 'get', fields: step.fields,
      elements: step.fields.map(([name]) => ({name})), closest: () => region};
    for (const fn of listeners.submit) fn({target: form, submitter: null, preventDefault() {}});
    pending.shift()();
    await settle();
    const a = document.activeElement;
    const live = page.querySelector('#arcade-status');
    logs.push({tag: a.tagName, id: a.id || null, name: a.name || null, value: a.value || null,
      text: (a.text || '').trim(), checked: 'checked' in (a.attrs || {}),
      inRegion: a.closest ? (a.closest('[data-region]') || {}).attrs?.['data-region'] : null,
      status: live ? live.textContent : null, writes: live ? live.writes || [] : null,
      sameStatus: live === status});
  }
  process.stdout.write(JSON.stringify(logs));
})().catch(e => { console.error(e.stack); process.exit(1); });
"""


def run(client, start, steps, responses):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is needed to run the home page script")
    payload = {
        "base": BASE, "start": start, "script": str(SCRIPT), "steps": steps,
        "page": Page(client.get(start).text).nodes,
        "responses": {path: Page(html).nodes for path, html in responses.items()},
    }
    out = subprocess.run([node, "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True,
                         timeout=30, check=False)
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def served(client, *paths):
    return {path: client.get(path).text for path in paths}


# --- Focus restore -------------------------------------------------------------------------------------------

def test_enter_on_compare_keeps_focus_on_compare_button(client):
    log, = run(client, "/", [{"region": "planet-duel", "focus": 'button[type="submit"]', "fields": DUEL_FIELDS}],
               served(client, DUEL_URL))
    assert log["tag"] == "BUTTON", log
    assert log["text"] == "Compare"
    assert log["inRegion"] == "planet-duel"


_spec = importlib.util.spec_from_file_location("quiz_answer_focus_121",
                                               Path(__file__).with_name("test_quiz_answer_focus_121.py"))
_q121 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_q121)


# Supersedes test_quiz_answer_focus_121.py::test_other_focus_and_missing_result_fallback: the same rows on the same
# #121 harness, except Compare, which now keeps focus (checked on this file's harness, which models the whole DOM).
@pytest.mark.parametrize("region,focus,fields,start,answer,tag,id_", [
    ("planet-quiz", None, [["round", "1"]], "/", "/?round=1&choice=earth", "BODY", None),
    ("planet-quiz", 'button[name="choice"]', [["round", "2"]], "/", "/?round=2&choice=jupiter", "BODY", None),
    ("planet-quiz", 'button[name="choice"]', [["round", "2"]], "/", "/?round=2", "BUTTON", None),
    ("planet-duel", "#duel-left-mars", [["left", "mars"], ["right", "earth"]],
     "/", "/?left=mars&right=earth", "INPUT", "duel-left-mars"),
    ("shelf-sort", "#planet-sort", [["sort", "diameter"]], "/", "/?sort=diameter", "SELECT", "planet-sort"),
])
def test_other_focus_and_missing_result_fallback_123(client, region, focus, fields, start, answer, tag, id_):
    step = {"region": region, "focus": focus, "fields": fields}
    if region == "planet-quiz" and "choice=" in answer:
        step["choice"] = "earth" if focus is None else "jupiter"
    log, = _q121.run(client, start, [step], [answer])
    assert log["tag"] == tag
    if id_:
        assert log["attrs"]["id"] == id_
        assert log["options"] == {"preventScroll": True}


def test_compare_on_mars_earth_keeps_focus_on_compare_not_mercury(client):
    log, = run(client, "/", [{"region": "planet-duel", "focus": "button",
                              "fields": [["left", "mars"], ["right", "earth"]]}],
               served(client, "/?left=mars&right=earth"))
    assert log["tag"] == "BUTTON" and log["text"] == "Compare", log
    assert log["id"] != "duel-left-mercury"
    assert log["inRegion"] == "planet-duel"


def test_compare_from_a_bookmarked_pair_keeps_focus_on_compare(client):
    start = "/?left=mars&right=earth"
    log, = run(client, start, [{"region": "planet-duel", "focus": 'button[type="submit"]',
                                "fields": [["left", "mars"], ["right", "jupiter"]]}],
               served(client, "/?left=mars&right=jupiter"))
    assert log["tag"] == "BUTTON" and log["text"] == "Compare", log


@pytest.mark.parametrize("radio,fields", [
    ("#duel-right-venus", DUEL_FIELDS),
    ("#duel-left-saturn", DUEL_FIELDS),
    ("#duel-left-mars", [["left", "mars"], ["right", "earth"]]),
])
def test_arrow_key_radio_choice_keeps_focus_on_the_checked_radio(client, radio, fields):
    # Arrow keys move focus and checked together; the change submits the form with that radio focused.
    url = "/?" + "&".join(f"{k}={v}" for k, v in fields)
    log, = run(client, "/", [{"region": "planet-duel", "focus": radio, "fields": fields}], served(client, url))
    assert log["tag"] == "INPUT", log
    assert "#" + log["id"] == radio
    assert log["checked"]


def test_birthday_submit_keeps_focus_on_its_unnamed_button(client):
    log, = run(client, "/", [{"region": "birthday-booth", "focus": 'button[type="submit"]',
                              "fields": [["sort", "order"], ["age", "10"]]}],
               served(client, "/?sort=order&age=10"))
    assert log["tag"] == "BUTTON" and log["text"] == "Find my planet ages", log


def test_control_whose_text_changed_is_found_by_position(client):
    # Neither id, name nor text matches, so the rule falls back to the same index among focusable controls.
    fresh = client.get(DUEL_URL).text.replace(">Compare</button>", ">Compare again</button>")
    assert ">Compare again</button>" in fresh
    log, = run(client, "/", [{"region": "planet-duel", "focus": 'button[type="submit"]', "fields": DUEL_FIELDS}],
               {DUEL_URL: fresh})
    assert log["tag"] == "BUTTON" and log["text"] == "Compare again", log


def test_unnamed_link_is_found_by_tag_and_text(client):
    # "or try age 10" has no id or name and sits after the age field and button.
    log, = run(client, "/", [{"region": "birthday-booth", "focus": "a.birthday-try",
                              "fields": [["sort", "order"], ["age", "10"]]}],
               served(client, "/?sort=order&age=10"))
    assert log["tag"] == "A" and log["text"] == "or try age 10", log


# --- Persistent status -----------------------------------------------------------------------------------------

@pytest.mark.parametrize("path", ["/", DUEL_URL, "/?age=10", "/?round=1&choice=earth", "/?left=mars&right=mars",
                                  "/?left=pluto&right=mars"])
def test_one_status_outside_every_region(client, path):
    nodes = Page(client.get(path).text).nodes
    outside = [n for n in nodes if n["attrs"].get("role") == "status" and n["region"] is None]
    assert len(outside) == 1
    status = outside[0]
    assert status["attrs"].get("id") == "arcade-status"
    assert status["attrs"].get("aria-live") == "polite"
    assert "visually-hidden" in status["attrs"].get("class", "").split()
    assert status["text"].strip() == ""
    assert not any(n["attrs"].get("id") == "arcade-status" for n in nodes if n["region"] is not None)
    # It is inside <main>, not in a data-region.
    parent = status["parent"]
    assert nodes[parent]["tag"] == "main"


def test_duel_compare_writes_the_ratio_sentence_to_status(client):
    log, = run(client, "/", [{"region": "planet-duel", "focus": 'button[type="submit"]', "fields": DUEL_FIELDS}],
               served(client, DUEL_URL))
    assert log["sameStatus"], "the status element must persist across swaps"
    assert log["status"] == SATURN_VENUS
    # Cleared first so the same sentence is announced again.
    assert log["writes"][0] == ""


def test_same_duel_twice_reannounces(client):
    step = {"region": "planet-duel", "focus": 'button[type="submit"]', "fields": DUEL_FIELDS}
    first, second = run(client, "/", [step, step], served(client, DUEL_URL))
    assert first["status"] == second["status"] == SATURN_VENUS
    assert second["writes"] == ["", SATURN_VENUS, "", SATURN_VENUS]


def test_same_planet_duel_status(client):
    log, = run(client, "/", [{"region": "planet-duel", "focus": "#duel-right-mars",
                              "fields": [["left", "mars"], ["right", "mars"]]}],
               served(client, "/?left=mars&right=mars"))
    assert log["status"] == "Both picks are Mars, so they are exactly the same size."


def test_birthday_age_10_writes_one_line_summary_to_status(client):
    log, = run(client, "/", [{"region": "birthday-booth", "focus": "#earth-age",
                              "fields": [["sort", "order"], ["age", "10"]]}],
               served(client, "/?sort=order&age=10"))
    assert log["sameStatus"]
    assert "\n" not in log["status"]
    assert AGES_10 in log["status"]
    assert len(log["status"]) < 200


def test_section_without_a_result_clears_stale_status(client):
    steps = [{"region": "planet-duel", "focus": 'button[type="submit"]', "fields": DUEL_FIELDS},
             {"region": "shelf-sort", "focus": "#planet-sort", "fields": [["sort", "diameter"]]}]
    first, second = run(client, "/", steps, served(client, DUEL_URL, DUEL_URL + "&sort=diameter"))
    assert first["status"] == SATURN_VENUS
    assert second["status"] == ""
    assert second["id"] == "planet-sort"


STATUS_LINE = '    <p id="arcade-status" class="visually-hidden" role="status" aria-live="polite"></p>\n'
ZOOM_BLOCK = re.compile(r'\n *<a class="scale-zoom".*?</a>(?=\n)', re.DOTALL)
COUNT_BLOCK = re.compile(r'\n *\n *<div class="duel-count".*?</div>\n *(?=\n)', re.DOTALL)
RING_PAIR = re.compile(r'<span class="duel-earth-ring" style="--ring: [\d.]+%">'
                       r'<span class="duel-earth-ring-label">Earth, same scale</span></span>')
NOTE_NOW = re.compile(r'<p class="duel-scale-note">Full circle = [A-Z][a-z]+, [\d,]+ km</p>')
NOTE_BEFORE = ('<p class="duel-scale-note">Drawn to scale for this pair only: '
               "the larger planet always fills the same circle.</p>")


# Supersedes test_duel_earth_ring.py::test_page_is_unchanged_apart_from_row_zoom_ring_and_note: same pages and
# digests, so everything except the status line, row, zoom link, Earth ring and reworded note stays byte-for-byte.
@pytest.mark.parametrize(("url", "status", "zooms", "blocks", "rings", "digest"), [
    ("/", 200, 1, 1, 1, "8a3828c60cf98b247ef920341a0b49347a756f13e6284047320accb8eefc2d4f"),
    ("/?left=mars&right=neptune", 200, 1, 1, 1, "b40575cda9a95d103dbe420300255d1a58c2367d0cb84c1d1e21ffa20687982b"),
    ("/?left=mars&right=earth", 200, 1, 1, 1, "d2d635e5603c175605df376f27a26f04f69236a513ad6b7c19430ca2399e29ec"),
    ("/?round=1&choice=earth", 200, 1, 1, 1, "0848700c8eef150b43c93e2163d873ba84caba8f011bd05baf2ffbcaacad2465"),
    ("/?left=pluto", 422, 1, 0, 0, "66553c68e4b191a5e080fedb98374bc297b1e9c80fff6d6b2da929f4a7a8adb5"),
])
def test_page_is_unchanged_apart_from_status_row_zoom_ring_and_note(client, url, status, zooms, blocks, rings,
                                                                    digest):
    response = client.get(url)
    assert response.status_code == status
    assert response.text.count(STATUS_LINE) == 1
    rest = response.text.replace(STATUS_LINE, "", 1)
    rest, found_zoom = ZOOM_BLOCK.subn("", rest)
    assert found_zoom == zooms
    rest, found = COUNT_BLOCK.subn("", rest)
    assert found == blocks
    rest, found_rings = RING_PAIR.subn("", rest)
    assert found_rings == rings
    rest, found_notes = NOTE_NOW.subn(NOTE_BEFORE, rest)
    assert found_notes == (1 if status == 200 else 0)
    assert sha256(rest.encode()).hexdigest() == digest


def test_visually_hidden_rule_keeps_status_off_screen():
    css = (ROOT / "static" / "arcade.css").read_text()
    match = re.search(r"\.visually-hidden\s*\{([^}]*)\}", css)
    assert match, "arcade.css needs a .visually-hidden rule"
    rule = re.sub(r"\s+", " ", match.group(1))
    for decl in ("position: absolute", "width: 1px", "height: 1px", "overflow: hidden", "white-space: nowrap"):
        assert decl in rule, decl
    assert "clip" in rule
    assert "display: none" not in rule and "visibility: hidden" not in rule


def test_plain_get_and_smoke_routes_still_work(client):
    assert SATURN_VENUS.replace("10.0", "<strong>10.0</strong>") in client.get(DUEL_URL).text
    assert client.get("/healthz").status_code == 200
    assert client.get("/convert?value=1&src=km&dst=mi").status_code == 200


# --- Real browser (skips without Playwright) -------------------------------------------------------------------

def _browser(client, javascript=True, width=1000):
    sync_api = pytest.importorskip("playwright.sync_api")

    def serve(route):
        response = client.get(route.request.url[len(BASE):])
        route.fulfill(status=response.status_code, body=response.content,
                      content_type=response.headers.get("content-type"))

    playwright = sync_api.sync_playwright().start()
    browser = playwright.chromium.launch()
    page = browser.new_page(java_script_enabled=javascript, viewport={"width": width, "height": 800})
    page.route("**/*", serve)

    def close():
        browser.close()
        playwright.stop()

    return page, close


def test_browser_enter_on_compare_keeps_focus_and_announces(client):
    page, close = _browser(client)
    try:
        page.goto(BASE + "/?left=mars&right=earth")
        page.evaluate("document.querySelector('#duel-left-saturn').checked = true")
        page.evaluate("document.querySelector('#duel-right-venus').checked = true")
        compare = page.locator(".duel-form button[type=submit]")
        compare.focus()
        compare.press("Enter")
        page.wait_for_url("**/*left=saturn*")
        page.wait_for_function("document.getElementById('arcade-status').textContent.length > 0")
        assert compare.evaluate("el => el === document.activeElement")
        assert page.locator("#arcade-status").text_content() == SATURN_VENUS
        tree = page.context.new_cdp_session(page).send("Accessibility.getFullAXTree")["nodes"]
        assert any(n.get("role", {}).get("value") == "status"
                   and n.get("name", {}).get("value", "") in ("", SATURN_VENUS) for n in tree)
    finally:
        close()


def test_browser_arrow_key_radio_keeps_focus_on_checked_radio(client):
    page, close = _browser(client)
    try:
        page.goto(BASE + "/?left=mars&right=earth")
        radio = page.locator("#duel-left-mars")
        radio.focus()
        radio.press("ArrowRight")
        page.wait_for_url("**/*left=jupiter*")
        page.wait_for_function("document.getElementById('arcade-status').textContent.length > 0")
        jupiter = page.locator("#duel-left-jupiter")
        assert jupiter.evaluate("el => el === document.activeElement && el.checked")
        assert page.locator("#arcade-status").text_content().startswith("Jupiter is ")
    finally:
        close()


def test_browser_birthday_status(client):
    page, close = _browser(client)
    try:
        page.goto(BASE + "/")
        age = page.locator("#earth-age")
        age.fill("10")
        age.press("Enter")
        page.wait_for_url("**/*age=10*")
        page.wait_for_function("document.getElementById('arcade-status').textContent.length > 0")
        assert AGES_10 in page.locator("#arcade-status").text_content()
        assert age.evaluate("el => el === document.activeElement")
    finally:
        close()


@pytest.mark.parametrize("focused_answer", [True, False], ids=["keyboard-answer", "outside-focus"])
def test_browser_focus_across_quiz_duel_and_shelf_123(client, focused_answer):
    """Stricter successor of the #121 cross-section test: Compare now keeps its own focus."""
    page, close = _browser(client)
    try:
        page.goto(BASE + "/?round=1&score=0")
        radio = page.locator("#duel-left-mars")
        radio.focus()
        radio.press("Space")
        page.wait_for_url("**/*left=mars*")
        assert radio.evaluate("el => el === document.activeElement && el.checked")

        compare = page.locator(".duel-form button")
        compare.focus()
        page.evaluate("document.querySelector('.duel-form [name=right][value=jupiter]').checked = true")
        compare.press("Enter")
        page.wait_for_url("**/*right=jupiter*")
        page.wait_for_function("document.getElementById('arcade-status').textContent.includes('Jupiter')")
        assert compare.evaluate("el => el === document.activeElement")
        assert not page.locator("#duel-left-mercury").evaluate("el => el === document.activeElement")

        shelf = page.locator("#planet-sort")
        shelf.select_option("diameter")
        shelf.focus()
        page.evaluate("document.querySelector('[data-region=shelf-sort]').requestSubmit()")
        page.wait_for_url("**/*sort=diameter*")
        assert shelf.evaluate("el => el === document.activeElement")

        answer = page.locator('.planet-quiz button[name="choice"][value="earth"]')
        if focused_answer:
            answer.focus()
        before = page.evaluate("window.scrollY")
        if focused_answer:
            answer.press("Enter")
        else:
            answer.evaluate("el => el.form.requestSubmit(el)")
        status = page.locator('.planet-quiz [role="status"]')
        status.wait_for()
        assert "You chose Earth" in status.inner_text()
        target = page.locator(".planet-quiz a.quiz-next[href]") if focused_answer else shelf
        assert target.evaluate("el => el === document.activeElement")
        page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        assert page.evaluate("window.scrollY") == before
    finally:
        close()


@pytest.mark.parametrize("path", ["/", DUEL_URL, "/?age=10"])
def test_browser_status_has_no_visible_footprint(client, path):
    page, close = _browser(client)
    try:
        page.goto(BASE + path)
        box = page.locator("#arcade-status").bounding_box()
        assert box is not None and box["width"] <= 1 and box["height"] <= 1
        first = page.locator("main > section").first.bounding_box()
        page.evaluate("document.getElementById('arcade-status').remove()")
        assert page.locator("main > section").first.bounding_box() == first
    finally:
        close()
