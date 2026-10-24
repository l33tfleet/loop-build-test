"""#56: run static/arcade.js against the real pages and tap controls, checking the page stays put.

Node runs the script in a small fake page built from the server's HTML: each data-region is a block whose
height follows its HTML length, stacked top to bottom. Fetches answer with the server's real response.
"""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "static" / "arcade.js"
BASE = "http://testserver"

HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const REGION = /<(section|form)\b[^>]*data-region="([\w-]+)"[^>]*>[\s\S]*?<\/\1>/g;

class Region {
  constructor(name, html) { this.name = name; this.outerHTML = html; this.height = Math.round(html.length / 10); }
  getAttribute(attr) { return attr === "data-region" ? this.name : null; }
  closest(sel) { return sel === "[data-region]" ? this : null; }
  contains(node) { return node === this || (node != null && node.region === this); }
  querySelector() { return null; }
  getBoundingClientRect() {
    let top = -win.scrollY;
    for (const r of page.regions) { if (r === this) break; top += r.height; }
    return { top, bottom: top + this.height };
  }
  replaceWith(fresh) { page.regions[page.regions.indexOf(this)] = fresh; }
}

function parse(html) {
  const regions = [...html.matchAll(REGION)].map((m) => new Region(m[2], m[0]));
  return {
    regions,
    querySelector(sel) {
      const m = /^\[data-region="([\w-]+)"\]$/.exec(sel);
      return (m && regions.find((r) => r.name === m[1])) || null;
    },
    querySelectorAll(sel) { if (sel !== "[data-region]") throw new Error(sel); return regions.slice(); },
  };
}

const page = parse(input.page);
const listeners = {};
const log = { fetched: [], navigated: [], pushed: [], scrolls: [], prevented: [] };
const pending = [];
const win = {
  scrollY: 0,
  location: { href: input.base + "/", origin: input.base, assign(url) { log.navigated.push(url); } },
  scrollBy(x, y) { log.scrolls.push(y); win.scrollY += y; },
  addEventListener(type, fn) { (listeners["window:" + type] ||= []).push(fn); },
};
const document = {
  activeElement: null,
  addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
  querySelector: (sel) => page.querySelector(sel),
  querySelectorAll: (sel) => page.querySelectorAll(sel),
  contains: (node) => page.regions.some((r) => r.contains(node)),
  adoptNode: (node) => node,
};
class FormData {
  constructor(form) { this.pairs = form.fields.map((p) => p.slice()); }
  append(k, v) { this.pairs.push([k, v]); }
  [Symbol.iterator]() { return this.pairs[Symbol.iterator](); }
}
const context = vm.createContext({
  window: win, document, history: { pushState(s, t, url) { log.pushed.push(url); win.location.href = url; } },
  fetch(url) {
    const path = url.slice(input.base.length);
    log.fetched.push(path);
    return new Promise((resolve, reject) => pending.push(() => {
      if (!(path in input.responses)) return reject(new Error("no response for " + path));
      resolve({ text: async () => input.responses[path] });
    }));
  },
  DOMParser: class { parseFromString(html) { return parse(html); } },
  FormData, URL, URLSearchParams, CSS: { escape: (s) => String(s).replace(/["\\]/g, "\\$&") },
});
vm.runInContext(fs.readFileSync(input.script, "utf8"), context);

function regionNamed(name) { return page.regions.find((r) => r.name === name); }
function control(region, props) {
  return Object.assign({ region, closest(sel) { return sel === "[data-region]" ? region : (sel === "a[href]" && this.href ? this : null); } }, props);
}
function dispatch(type, props) {
  const event = Object.assign({ type, button: 0, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } }, props);
  for (const fn of listeners[type] || []) fn(event);
  log.prevented.push(event.defaultPrevented);
}
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

(async () => {
  for (const step of input.steps) {
    if (step.do === "scrollTo") win.scrollY = step.y;
    else if (step.do === "scroll") win.scrollY += step.by;
    else if (step.do === "submit") {
      const form = control(regionNamed(step.region), { action: input.base + "/", method: "get", fields: step.fields });
      const submitter = step.submitter ? { name: step.submitter[0], value: step.submitter[1] } : null;
      dispatch("submit", { target: form, submitter });
    } else if (step.do === "click") {
      dispatch("click", { target: control(regionNamed(step.region), { href: input.base + step.href, target: "" }) });
    } else if (step.do === "respond") {
      while (pending.length) pending.shift()();
      await settle();
    } else if (step.do === "measure") {
      log[step.as] = regionNamed(step.region).getBoundingClientRect().top;
    }
  }
  log.scrollY = win.scrollY;
  log.regions = Object.fromEntries(page.regions.map((r) => [r.name, r.outerHTML]));
  log.order = page.regions.map((r) => r.name);
  process.stdout.write(JSON.stringify(log));
})();
"""


def run(client, steps, responses, start="/"):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is needed to run the home page script")
    payload = {
        "base": BASE,
        "script": str(SCRIPT),
        "page": client.get(start).text,
        "responses": {path: client.get(path).text for path in responses},
        "steps": steps,
    }
    out = subprocess.run(
        [node, "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, timeout=30, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def text(html):
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html))


def test_quiz_answer_updates_only_the_quiz_in_place(client):
    log = run(client, [
        {"do": "scrollTo", "y": 400},
        {"do": "measure", "region": "planet-quiz", "as": "before"},
        {"do": "submit", "region": "planet-quiz", "fields": [["round", "1"]], "submitter": ["choice", "jupiter"]},
        {"do": "respond"},
        {"do": "measure", "region": "planet-quiz", "as": "after"},
    ], ["/?round=1&choice=jupiter"])
    assert log["prevented"] == [True]
    assert log["navigated"] == []
    assert log["fetched"] == ["/?round=1&choice=jupiter"]
    assert log["pushed"] == [BASE + "/?round=1&choice=jupiter"]
    assert "Correct" in text(log["regions"]["planet-quiz"])
    assert "Jupiter has the larger diameter." in text(log["regions"]["planet-quiz"])
    assert log["after"] == log["before"]
    assert log["scrollY"] == 400
    assert log["order"] == ["planet-duel", "planet-quiz", "birthday-booth", "shelf-sort", "planet-shelf"]


def test_next_link_updates_the_quiz_in_place(client):
    log = run(client, [
        {"do": "scrollTo", "y": 300},
        {"do": "measure", "region": "planet-quiz", "as": "before"},
        {"do": "click", "region": "planet-quiz", "href": "/?round=2"},
        {"do": "respond"},
        {"do": "measure", "region": "planet-quiz", "as": "after"},
    ], ["/?round=2"])
    assert log["prevented"] == [True]
    assert log["navigated"] == []
    assert log["fetched"] == ["/?round=2"]
    assert "Round 2 of 3" in text(log["regions"]["planet-quiz"])
    assert log["after"] == log["before"]


def test_shelf_order_updates_in_place(client):
    log = run(client, [
        {"do": "scrollTo", "y": 900},
        {"do": "measure", "region": "shelf-sort", "as": "before"},
        {"do": "submit", "region": "shelf-sort", "fields": [["sort", "diameter"]]},
        {"do": "respond"},
        {"do": "measure", "region": "shelf-sort", "as": "after"},
    ], ["/?sort=diameter"])
    assert log["prevented"] == [True]
    assert log["navigated"] == []
    assert log["fetched"] == ["/?sort=diameter"]
    assert "Largest diameter first" in text(log["regions"]["planet-shelf"])
    assert log["after"] == log["before"]


def test_tapped_section_stays_put_when_a_section_above_changes_height(client):
    # The quiz form does not carry the duel picks, so the duel above resets and changes height.
    start = "/?left=jupiter&right=mercury"
    log = run(client, [
        {"do": "scrollTo", "y": 500},
        {"do": "measure", "region": "planet-quiz", "as": "before"},
        {"do": "submit", "region": "planet-quiz", "fields": [["round", "1"]], "submitter": ["choice", "mars"]},
        {"do": "respond"},
        {"do": "measure", "region": "planet-quiz", "as": "after"},
    ], ["/?round=1&choice=mars"], start=start)
    assert client.get(start).text != client.get("/").text
    assert log["scrolls"] and log["scrolls"][-1] != 0, "duel height did not change; pick another start page"
    assert log["after"] == log["before"]


def test_scrolling_while_the_answer_loads_is_kept(client):
    log = run(client, [
        {"do": "scrollTo", "y": 400},
        {"do": "submit", "region": "planet-quiz", "fields": [["round", "1"]], "submitter": ["choice", "jupiter"]},
        {"do": "scroll", "by": 300},
        {"do": "measure", "region": "planet-quiz", "as": "before"},
        {"do": "respond"},
        {"do": "measure", "region": "planet-quiz", "as": "after"},
    ], ["/?round=1&choice=jupiter"])
    assert log["navigated"] == []
    assert "Correct" in text(log["regions"]["planet-quiz"])
    assert log["scrollY"] == 700
    assert log["after"] == log["before"]
    assert all(y == 0 for y in log["scrolls"])


def test_failed_fetch_falls_back_to_a_normal_page_load(client):
    log = run(client, [
        {"do": "click", "region": "birthday-booth", "href": "/?age=10"},
        {"do": "respond"},
    ], [])
    assert log["prevented"] == [True]
    assert log["navigated"] == [BASE + "/?age=10"]
