"""#121: restore quiz answer focus to the rendered continuation, without scrolling."""
import json
import shutil
import subprocess
from html.parser import HTMLParser
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "static/arcade.js"


class Regions(HTMLParser):
    """Extract real server markup; Node supplies only the DOM operations arcade.js uses."""

    def __init__(self, html):
        super().__init__(convert_charrefs=True)
        self.regions = []
        self.region = None
        self.stack = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-region" in attrs:
            self.region = {"name": attrs["data-region"], "nodes": [], "html": ""}
            self.regions.append(self.region)
        if self.region is None:
            return
        self.region["html"] += self.get_starttag_text()
        node = {"tag": tag, "attrs": attrs, "text": ""}
        self.region["nodes"].append(node)
        if tag not in {"input", "br", "img", "hr"}:
            self.stack.append(node)

    def handle_data(self, data):
        if self.region is not None:
            self.region["html"] += data
            for node in self.stack:
                node["text"] += data

    def handle_endtag(self, tag):
        if self.region is None:
            return
        self.region["html"] += f"</{tag}>"
        while self.stack:
            if self.stack.pop()["tag"] == tag:
                break
        if not self.stack:
            self.region = None


HARNESS = r"""
const fs = require('fs'), vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const listeners = {}, pending = [], logs = [];
const body = {tagName: 'BODY'};
let page;
const document = {
  activeElement: body,
  addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
  querySelector: sel => page.querySelector(sel),
  querySelectorAll: sel => page.querySelectorAll(sel),
  contains: node => node === body || page.regions.some(r => r.contains(node)),
  adoptNode: node => node,
};
class Node {
  constructor(data, region) {
    this.tagName = data.tag.toUpperCase(); this.attrs = {...data.attrs};
    this.initial = JSON.stringify(this.attrs); this.textContent = data.text; this.region = region;
    this.events = {};
  }
  get id() { return this.attrs.id || ''; }
  get name() { return this.attrs.name || ''; }
  get value() { return this.attrs.value || ''; }
  get type() { return this.attrs.type || ''; }
  getAttribute(key) { return this.attrs[key] ?? null; }
  setAttribute(key, value) { this.attrs[key] = value; }
  removeAttribute(key) { delete this.attrs[key]; }
  addEventListener(type, fn) { (this.events[type] ||= []).push(fn); }
  matches(sel) {
    return sel.split(',').some(s => {
      s = s.trim();
      const tag = /^[\w-]+/.exec(s);
      if (tag && tag[0].toUpperCase() !== this.tagName) return false;
      const id = /#([\w-]+)/.exec(s);
      if (id && id[1] !== this.id) return false;
      const cls = /\.([\w-]+)/.exec(s);
      if (cls && !(this.attrs.class || '').split(' ').includes(cls[1])) return false;
      return [...s.matchAll(/\[([\w-]+)(?:="([^"]*)")?\]/g)].every(
        m => m[1] in this.attrs && (m[2] === undefined || this.attrs[m[1]] === m[2]));
    });
  }
  closest(sel) { return sel === '[data-region]' ? this.region : (this.matches(sel) ? this : null); }
  focus(options) {
    if ('disabled' in this.attrs || !document.contains(this)) return;
    const old = document.activeElement;
    document.activeElement = this;
    for (const fn of old.events?.blur || []) fn();
    this.focusOptions = options;
  }
}
class Region {
  constructor(data) {
    this.name = data.name; this.html = data.html;
    this.nodes = data.nodes.map(n => new Node(n, this));
  }
  get outerHTML() {
    return this.html + this.nodes.filter(n => JSON.stringify(n.attrs) !== n.initial)
      .map(n => JSON.stringify(n.attrs)).join('');
  }
  getAttribute(key) { return key === 'data-region' ? this.name : null; }
  contains(node) { return node === this || this.nodes.includes(node); }
  closest() { return this; }
  querySelector(sel) { return this.nodes.find(n => n.matches(sel)) || null; }
  getBoundingClientRect() {
    let top = -win.scrollY;
    for (const r of page.regions) { if (r === this) break; top += r.html.length / 10; }
    return {top, bottom: top + this.html.length / 10};
  }
  replaceWith(fresh) {
    if (this.contains(document.activeElement)) document.activeElement = body;
    page.regions[page.regions.indexOf(this)] = fresh;
  }
}
function parse(data) {
  const regions = data.map(r => new Region(r));
  return {
    regions,
    querySelector(sel) {
      const m = /^\[data-region="([\w-]+)"\]$/.exec(sel);
      return m ? regions.find(r => r.name === m[1]) : null;
    },
    querySelectorAll() { return regions.slice(); },
  };
}
page = parse(input.page);
const win = {
  scrollY: 450,
  location: {href: 'http://testserver' + input.start + '#quiz-title', origin: 'http://testserver',
    hash: '#quiz-title', assign(url) { throw new Error('unexpected navigation: ' + url); }},
  scrollBy(x, y) { this.scrollY += y; },
  addEventListener(type, fn) { listeners['window:' + type] = [fn]; },
};
vm.runInNewContext(fs.readFileSync(input.script, 'utf8'), {
  document, window: win, URL, CSS: {escape: s => s},
  history: {pushState(s, t, url) { win.location.href = url; }},
  FormData: class {
    constructor(form) { this.pairs = form.fields.slice(); }
    append(k, v) { this.pairs.push([k, v]); }
    [Symbol.iterator]() { return this.pairs[Symbol.iterator](); }
  },
  fetch: url => new Promise(resolve => pending.push(() => {
    const path = new URL(url).pathname + new URL(url).search;
    if (!input.responses[path]) throw new Error('unexpected fetch: ' + path);
    resolve({text: async () => input.responses[path]});
  })),
  DOMParser: class { parseFromString(data) { return parse(data); } },
});
(async () => {
  for (const step of input.steps) {
    const region = page.regions.find(r => r.name === step.region);
    const quiz = page.regions.find(r => r.name === 'planet-quiz');
    const status = quiz.querySelector('.quiz-answer[role="status"]');
    if (step.focus) region.querySelector(step.focus).focus({preventScroll: true});
    const form = {action: 'http://testserver/', method: 'get', fields: step.fields,
      elements: step.fields.map(([name]) => ({name})), closest: () => region};
    const submitter = step.choice ? region.querySelector('button[name="choice"][value="' + step.choice + '"]') : null;
    const before = region.getBoundingClientRect().top;
    for (const fn of listeners.submit) fn({target: form, submitter, preventDefault() {}});
    win.scrollY += 75; // A scroll during fetch must also survive the swap.
    pending.shift()();
    await new Promise(resolve => setTimeout(resolve, 0));
    const active = document.activeElement;
    const current = page.regions.find(r => r.name === step.region);
    const answered = page.regions.find(r => r.name === 'planet-quiz');
    logs.push({tag: active.tagName, attrs: active.attrs, text: active.textContent,
      options: active.focusOptions, scrollDelta: current.getBoundingClientRect().top - before,
      url: win.location.href, status: answered.querySelector('.quiz-answer[role="status"]')?.textContent,
      sameQuiz: answered === quiz, sameStatus: answered.querySelector('.quiz-answer[role="status"]') === status});
  }
  process.stdout.write(JSON.stringify(logs));
})();
"""


def run(client, start, steps, responses):
    assert shutil.which("node"), "Node is required for offline arcade.js coverage"
    payload = {"script": str(SCRIPT), "start": start, "page": Regions(client.get(start).text).regions,
                   "steps": steps, "responses": {p: Regions(client.get(p).text).regions for p in responses}}
    result = subprocess.run(["node", "-e", HARNESS], input=json.dumps(payload),
                            text=True, capture_output=True, timeout=20, check=False)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


@pytest.mark.parametrize("round_,score,set_,choice,label", [
    (1, 0, None, "earth", "Next"), (1, 0, None, "jupiter", "Next"),
    (3, 2, None, "uranus", "Play again"), (3, 1, None, "neptune", "Play again"),
    (2, 1, 1, "venus", "Next"), (3, 2, 2, "venus", "Play again"),
])
def test_answer_focuses_rendered_continuation(client, round_, score, set_, choice, label):
    fields = [["round", str(round_)], ["score", str(score)]]
    if set_ is not None:
        fields.append(["set", str(set_)])
    start = "/?" + "&".join(f"{k}={v}" for k, v in fields)
    answer = start + "&choice=" + choice
    step = {"region": "planet-quiz", "fields": fields, "choice": choice,
                "focus": f'button[name="choice"][value="{choice}"]'}
    log, = run(client, start, [step], [answer])
    rendered = Regions(client.get(answer).text).regions
    quiz = next(r for r in rendered if r["name"] == "planet-quiz")
    link = next(n for n in quiz["nodes"] if n["attrs"].get("class") == "quiz-next")
    assert log["tag"] == "A", log
    assert log["text"] == label
    assert log["attrs"]["href"] == link["attrs"]["href"]
    assert log["options"] == {"preventScroll": True}
    assert log["scrollDelta"] == pytest.approx(-75)
    assert log["url"].endswith("#quiz-title")
    assert "You chose" in log["status"]
    # Orca otherwise announces only the newly focused link, dropping the inserted status.
    assert log["attrs"].get("aria-description") == " ".join(log["status"].split())


@pytest.mark.parametrize("region,focus,fields,start,answer,tag,id_", [
    ("planet-quiz", None, [["round", "1"]], "/", "/?round=1&choice=earth", "BODY", None),
    ("planet-quiz", 'button[name="choice"]', [["round", "2"]], "/", "/?round=2&choice=jupiter", "BODY", None),
    ("planet-quiz", 'button[name="choice"]', [["round", "2"]], "/", "/?round=2", "BUTTON", None),
    ("planet-duel", "#duel-left-mars", [["left", "mars"], ["right", "earth"]],
     "/", "/?left=mars&right=earth", "INPUT", "duel-left-mars"),
    ("planet-duel", "button", [["left", "mars"], ["right", "earth"]],
     "/", "/?left=mars&right=earth", "INPUT", "duel-left-mercury"),
    ("shelf-sort", "#planet-sort", [["sort", "diameter"]], "/", "/?sort=diameter", "SELECT", "planet-sort"),
])
def test_other_focus_and_missing_result_fallback(client, region, focus, fields, start, answer, tag, id_):
    step = {"region": region, "focus": focus, "fields": fields}
    if region == "planet-quiz" and "choice=" in answer:
        step["choice"] = "earth" if focus is None else "jupiter"
    log, = run(client, start, [step], [answer])
    assert log["tag"] == tag
    if id_:
        assert log["attrs"]["id"] == id_
        assert log["options"] == {"preventScroll": True}


def test_answered_quiz_survives_unrelated_submissions(client):
    answer = "/?round=1&score=0&choice=earth"
    sorted_ = answer + "&sort=diameter"
    steps = [{"region": "planet-quiz", "focus": 'button[name="choice"][value="earth"]',
                  "choice": "earth", "fields": [["round", "1"], ["score", "0"]]},
             {"region": "shelf-sort", "focus": "#planet-sort", "fields": [["sort", "diameter"]]}]
    first, second = run(client, "/", steps, [answer, sorted_])
    assert first["tag"] == "A"
    assert second["sameQuiz"] and second["sameStatus"]
    assert second["attrs"]["id"] == "planet-sort"


def test_plain_get_and_smoke_routes(client):
    response = client.get("/?round=1&choice=earth")
    assert response.status_code == 200
    assert 'role="status"' in response.text and "You chose Earth" in response.text
    assert "Next</a>" in response.text
    assert client.get("/healthz").status_code == 200
    assert client.get("/convert?value=1&src=km&dst=mi").status_code == 200


def test_zero_score_final_answer_focuses_play_again(client):
    start = "/?round=3&score=0"
    answer = start + "&choice=neptune"
    step = {"region": "planet-quiz", "fields": [["round", "3"], ["score", "0"]],
            "choice": "neptune", "focus": 'button[name="choice"][value="neptune"]'}
    log, = run(client, start, [step], [answer])
    assert log["tag"] == "A", log
    assert log["text"] == "Play again"
    assert log["options"] == {"preventScroll": True}
    assert log["scrollDelta"] == pytest.approx(-75)
    assert "You chose Neptune" in log["status"]


def test_unfocused_quiz_answer_preserves_focus_in_another_region(client):
    duel = "/?left=mars&right=earth"
    answer = duel + "&round=1&choice=earth"
    steps = [
        {"region": "planet-duel", "fields": [["left", "mars"], ["right", "earth"]],
         "focus": "#duel-left-mars"},
        {"region": "planet-quiz", "fields": [["round", "1"]], "choice": "earth"},
    ]
    first, second = run(client, "/", steps, [duel, answer])
    assert first["attrs"]["id"] == second["attrs"]["id"] == "duel-left-mars"
    assert second["tag"] == "INPUT"
    assert "You chose Earth" in second["status"]


@pytest.mark.parametrize("round_,choice,label", [(1, "earth", "Next"), (3, "neptune", "Play again")])
def test_answer_focus_with_other_sections_in_bookmarked_url(client, round_, choice, label):
    start = f"/?left=mars&right=jupiter&sort=diameter&round={round_}&score=0"
    answer = start + "&choice=" + choice
    step = {"region": "planet-quiz", "fields": [["round", str(round_)], ["score", "0"]],
            "choice": choice, "focus": f'button[name="choice"][value="{choice}"]'}
    log, = run(client, start, [step], [answer])
    assert log["tag"] == "A", log
    assert log["text"] == label
    assert log["options"] == {"preventScroll": True}
    assert log["scrollDelta"] == pytest.approx(-75)
    assert "You chose" in log["status"]
    assert log["attrs"].get("aria-description") == " ".join(log["status"].split())
    assert log["url"] == "http://testserver" + answer + "#quiz-title"


@pytest.mark.parametrize("set_", range(3))
@pytest.mark.parametrize("round_", range(1, 4))
def test_each_rendered_answer_hands_focus_to_continuation(client, set_, round_):
    start = f"/?set={set_}&round={round_}&score=0"
    quiz = next(r for r in Regions(client.get(start).text).regions if r["name"] == "planet-quiz")
    choices = [n["attrs"]["value"] for n in quiz["nodes"]
               if n["tag"] == "button" and n["attrs"].get("name") == "choice"]
    assert len(choices) == 2
    for choice in choices:
        answer = start + "&choice=" + choice
        step = {"region": "planet-quiz", "fields": [["round", str(round_)], ["score", "0"]],
                "choice": choice, "focus": f'button[name="choice"][value="{choice}"]'}
        log, = run(client, start, [step], [answer])
        assert log["tag"] == "A", log
        assert log["text"] == ("Play again" if round_ == 3 else "Next")
        assert log["attrs"]["href"]
        assert log["options"] == {"preventScroll": True}
        assert log["scrollDelta"] == pytest.approx(-75)
        assert "You chose" in log["status"]
        assert log["attrs"].get("aria-description") == " ".join(log["status"].split())


@pytest.mark.parametrize("round_,choice,label", [(1, "earth", "Next"), (3, "neptune", "Play again")])
@pytest.mark.parametrize("javascript", [True, False], ids=["in-place", "plain-get"])
def test_keyboard_answer_in_browser(client, round_, choice, label, javascript):
    """Exercise native Enter submission, focus, layout and the accessibility tree offline."""
    sync_api = pytest.importorskip("playwright.sync_api")
    base = "http://testserver"

    def serve(route):
        response = client.get(route.request.url[len(base):])
        body = SCRIPT.read_bytes() if route.request.url == base + "/static/arcade.js" else response.content
        route.fulfill(status=response.status_code, body=body,
                      content_type=response.headers.get("content-type"))

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(java_script_enabled=javascript, viewport={"width": 1000, "height": 800})
            page.route("**/*", serve)
            page.goto(f"{base}/?round={round_}&score=0")
            answer = page.locator(f'.planet-quiz button[name="choice"][value="{choice}"]')
            answer.focus()
            before = page.evaluate("window.scrollY")
            assert before > 0, "answer must be below the fold to detect a scroll reset"
            page.evaluate("window.quizDocument = true")
            answer.press("Enter")
            status = page.locator('.planet-quiz [role="status"]')
            status.wait_for()
            assert f"You chose {choice.title()}" in status.inner_text()
            continuation = page.locator(".planet-quiz a.quiz-next[href]")
            assert continuation.inner_text() == label
            assert f"choice={choice}" in page.url
            if javascript:
                assert continuation.evaluate("el => el === document.activeElement")
                # Allow browser scroll anchoring and subsequent animation frames to settle.
                page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                assert page.evaluate("window.scrollY") == before
                assert page.evaluate("window.quizDocument") is True
                # Inspect what assistive technology receives, including the result on focus.
                session = page.context.new_cdp_session(page)
                tree = session.send("Accessibility.getFullAXTree")["nodes"]
                link = next(n for n in tree if n.get("role", {}).get("value") == "link"
                            and n.get("name", {}).get("value") == label)
                assert link["description"]["value"] == " ".join(status.inner_text().split())
                assert any(n.get("role", {}).get("value") == "status" for n in tree)
            else:
                assert page.evaluate("window.quizDocument === undefined")
        finally:
            browser.close()


@pytest.mark.parametrize("round_,choice,label", [(1, "earth", "Next"), (3, "neptune", "Play again")])
def test_quiz_answer_redirect_precedes_generic_id_restore(client, monkeypatch, round_, choice, label):
    """Choice buttons must use the continuation rule even when they have stable IDs."""
    original_init = Regions.__init__

    def with_answer_ids(self, html):
        original_init(self, html)
        for region in self.regions:
            for node in region["nodes"]:
                if node["tag"] == "button" and node["attrs"].get("name") == "choice":
                    node["attrs"]["id"] = "answer-" + node["attrs"]["value"]

    monkeypatch.setattr(Regions, "__init__", with_answer_ids)
    start = f"/?round={round_}&score=0"
    answer = start + "&choice=" + choice
    step = {"region": "planet-quiz", "fields": [["round", str(round_)], ["score", "0"]],
            "choice": choice, "focus": "#answer-" + choice}
    log, = run(client, start, [step], [answer])
    assert log["tag"] == "A", log
    assert log["text"] == label
    assert log["options"] == {"preventScroll": True}
    assert log["scrollDelta"] == pytest.approx(-75)
    assert log["attrs"].get("aria-description") == " ".join(log["status"].split())


@pytest.mark.parametrize("focused_answer", [True, False], ids=["keyboard-answer", "outside-focus"])
def test_browser_focus_across_quiz_duel_and_shelf(client, focused_answer):
    """Native focus survives other section updates, and quiz answers only move owned focus."""
    sync_api = pytest.importorskip("playwright.sync_api")
    base = "http://testserver"

    def serve(route):
        response = client.get(route.request.url[len(base):])
        body = SCRIPT.read_bytes() if route.request.url == base + "/static/arcade.js" else response.content
        route.fulfill(status=response.status_code, body=body,
                      content_type=response.headers.get("content-type"))

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1000, "height": 800})
            page.route("**/*", serve)
            page.goto(base + "/?round=1&score=0")

            # Radio change submits immediately; the selected radio must regain focus.
            radio = page.locator("#duel-left-mars")
            radio.focus()
            radio.press("Space")
            page.wait_for_url("**/*left=mars*")
            assert radio.evaluate("el => el === document.activeElement && el.checked")

            # Preserve the generic fallback used by Compare before the quiz change.
            compare = page.locator(".duel-form button")
            compare.focus()
            page.evaluate("document.querySelector('.duel-form [name=right][value=jupiter]').checked = true")
            compare.press("Enter")
            page.wait_for_url("**/*right=jupiter*")
            assert page.locator("#duel-left-mercury").evaluate("el => el === document.activeElement")

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
            browser.close()


@pytest.mark.parametrize("round_,label", [(1, "Next"), (3, "Play again")])
def test_tab_enter_answer_shows_continuation_focus_ring(client, round_, label):
    """The keyboard path in the evidence must leave a visible continuation focus ring."""
    sync_api = pytest.importorskip("playwright.sync_api")
    base = "http://testserver"

    def serve(route):
        response = client.get(route.request.url[len(base):])
        body = SCRIPT.read_bytes() if route.request.url == base + "/static/arcade.js" else response.content
        route.fulfill(status=response.status_code, body=body,
                      content_type=response.headers.get("content-type"))

    with sync_api.sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        try:
            page = browser.new_page(viewport={"width": 1000, "height": 800})
            page.route("**/*", serve)
            page.goto(f"{base}/?round={round_}")
            # Reach an answer with native sequential keyboard navigation, without focus().
            for _ in range(50):
                page.keyboard.press("Tab")
                if page.evaluate('document.activeElement.matches(\'.planet-quiz button[name="choice"]\')'):
                    break
            else:
                pytest.fail("Tab never reached a quiz answer")
            before = page.evaluate("window.scrollY")
            page.keyboard.press("Enter")
            status = page.locator('.planet-quiz [role="status"]')
            status.wait_for()
            continuation = page.get_by_role("link", name=label, exact=True)
            assert continuation.evaluate("el => el === document.activeElement")
            assert continuation.evaluate("el => el.matches(':focus-visible')")
            assert continuation.evaluate("el => getComputedStyle(el).outlineStyle") != "none"
            assert float(continuation.evaluate("el => parseFloat(getComputedStyle(el).outlineWidth)")) > 0
            page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
            assert page.evaluate("window.scrollY") == before
            assert "You chose" in status.inner_text()
        finally:
            browser.close()
