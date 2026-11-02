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
