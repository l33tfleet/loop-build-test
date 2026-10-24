"""#70: the Rocky planets jump link must reach its section even after Bar graph is picked.

Bar graph view hides the rocky inset (display: none), so a fragment jump to #inset-title has nothing to
scroll to. Node runs static/arcade.js in a small fake page built from the server's HTML and taps the
section links, checking the chart is back on circles (inset shown) before the browser follows the link.
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
const html = input.page;
const inset = /<section class="rocky-inset"[\s\S]*?<\/section>/.exec(html);

function element(id) {
  const at = html.indexOf('id="' + id + '"');
  if (at < 0) return null;
  const inInset = inset && at > inset.index && at < inset.index + inset[0].length;
  const tag = /<(\w+)[^<]*$/.exec(html.slice(0, at))[1];
  const el = {
    id, tagName: tag.toUpperCase(), checked: /<input\b[^>]*\bchecked\b/.test(html.slice(html.lastIndexOf("<", at), html.indexOf(">", at) + 1)),
    closest(sel) { return sel === ".rocky-inset" && inInset ? {} : null; },
    scrollIntoView() { log.scrolledTo.push(id); },
  };
  return el;
}
const elements = {};
for (const [, id] of html.matchAll(/\bid="([\w-]+)"/g)) elements[id] = element(id);
// Radios in one group: checking one unchecks the others.
for (const id of ["scale-view-circles", "scale-view-bars"]) {
  const el = elements[id];
  let checked = el.checked;
  Object.defineProperty(el, "checked", {
    get: () => checked,
    set(v) { checked = v; if (v) for (const other of ["scale-view-circles", "scale-view-bars"]) if (other !== id) elements[other].checked = false; },
  });
}

const listeners = {};
const log = { scrolledTo: [], prevented: [], fetched: [] };
const win = {
  location: { href: input.base + "/", origin: input.base, pathname: "/", hash: "" },
  addEventListener(type, fn) { (listeners["window:" + type] ||= []).push(fn); },
  scrollBy() {},
};
const document = {
  addEventListener(type, fn) { (listeners[type] ||= []).push(fn); },
  getElementById: (id) => elements[id] || null,
  querySelector: () => null,
  querySelectorAll: () => [],
};
const context = vm.createContext({
  window: win, location: win.location, document, history: { pushState() {} }, URL, URLSearchParams,
  fetch(url) { log.fetched.push(url); return new Promise(() => {}); },
  CSS: { escape: (s) => s },
});
vm.runInContext(fs.readFileSync(input.script, "utf8"), context);

function link(href) {
  const url = new URL(href, win.location.href);
  return {
    href: url.href, hash: url.hash, pathname: url.pathname, origin: url.origin, target: "",
    closest(sel) { return sel === "a[href]" ? this : null; },
  };
}
for (const step of input.steps) {
  if (step.do === "pick") elements[step.id].checked = true;
  else if (step.do === "click") {
    const event = { type: "click", button: 0, target: link(step.href), defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
    for (const fn of listeners.click || []) fn(event);
    log.prevented.push(event.defaultPrevented);
  } else if (step.do === "hash") {
    win.location.hash = step.hash;
    for (const fn of listeners["window:hashchange"] || []) fn({ type: "hashchange" });
  }
}
log.bars = elements["scale-view-bars"].checked;
log.circles = elements["scale-view-circles"].checked;
process.stdout.write(JSON.stringify(log));
"""


def run(client, steps):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is needed to run the home page script")
    payload = {"base": BASE, "script": str(SCRIPT), "page": client.get("/").text, "steps": steps}
    out = subprocess.run(
        [node, "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, timeout=30, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def nav_hrefs(client):
    nav = re.search(r'<nav aria-label="Sections"[^>]*>(.*?)</nav>', client.get("/").text, re.DOTALL).group(1)
    return {label: href for href, label in re.findall(r'<a href="(#[\w-]+)">([^<]+)</a>', nav)}


def test_rocky_planets_link_targets_the_inset_hidden_in_bar_view(client):
    # The case being guarded: the link's target sits inside the panel Bar graph view hides.
    assert nav_hrefs(client)["Rocky planets"] == "#inset-title"
    css = client.get("/static/arcade.css").text
    assert re.search(r"main:has\(#scale-view-bars:checked\) \.rocky-inset\s*\{[^}]*display:\s*none", css)


def test_rocky_planets_link_in_bar_view_brings_back_the_inset_before_the_jump(client):
    log = run(client, [{"do": "pick", "id": "scale-view-bars"}, {"do": "click", "href": "#inset-title"}])
    # Circles view shows the inset again; the browser's own fragment jump then has a box to scroll to.
    assert log["circles"] is True and log["bars"] is False
    assert log["prevented"] == [False]
    assert log["fetched"] == []


def test_rocky_planets_reached_by_hash_change_in_bar_view_is_revealed_and_scrolled_to(client):
    log = run(client, [{"do": "pick", "id": "scale-view-bars"}, {"do": "hash", "hash": "#inset-title"}])
    assert log["circles"] is True and log["bars"] is False
    assert log["scrolledTo"] == ["inset-title"]


@pytest.mark.parametrize("label", ["Duel", "Quiz", "Birthdays", "Scale", "Planets"])
def test_other_jump_links_leave_the_bar_view_alone(client, label):
    href = nav_hrefs(client)[label]
    log = run(client, [{"do": "pick", "id": "scale-view-bars"}, {"do": "click", "href": href}])
    assert log["bars"] is True and log["circles"] is False
    assert log["prevented"] == [False]


def test_rocky_planets_link_in_circle_view_changes_nothing(client):
    log = run(client, [{"do": "click", "href": "#inset-title"}, {"do": "hash", "hash": "#inset-title"}])
    assert log["circles"] is True and log["bars"] is False
    assert log["scrolledTo"] == []
