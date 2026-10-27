"""#81: the tagline's "bar graph" words link to the Diameter scale and switch it to Bar graph.

The tagline is the first "bar graph" text on the page, so a tap meant for the pill could land there and
jump to the top. Now it is a link to #scale-title; arcade.js ticks #scale-view-bars before the jump, and
without the script the link still jumps to the chart. Replaces the tagline checks that read raw markup.
"""
import json
import re
import shutil
import subprocess
from html import unescape
from pathlib import Path

import pytest

from tests.regressions.test_tagline_says_what_page_is_for import _lines

SCRIPT = Path(__file__).resolve().parents[2] / "static" / "arcade.js"
BASE = "http://testserver"
HEADER = re.compile(r"<header>(.*?)</header>", re.DOTALL)
TAGLINE = re.compile(r'<p class="tagline">(.*?)</p>', re.DOTALL)
VIEWPORT = 390
BODY_PAD = 16


def _markup(client):
    header = HEADER.search(client.get("/").text).group(1)
    match = TAGLINE.search(header)
    assert match, "no tagline under the title"
    return header, match.group(1)


def _text(markup):
    return " ".join(unescape(re.sub(r"<[^>]*>", "", markup)).split())


def test_tagline_link_points_at_the_diameter_scale(client):
    _, markup = _markup(client)
    links = re.findall(r"<a\b([^>]*)>(.*?)</a>", markup, re.DOTALL)
    assert len(links) == 1, markup
    attrs, words = links[0]
    assert re.fullmatch(r'\s*href="#scale-title"\s*', attrs), attrs
    assert words == "bar graph"
    assert 'id="scale-title"' in client.get("/").text


def test_tagline_text_is_unchanged_by_the_link(client):
    _, markup = _markup(client)
    assert _text(markup) == (
        "Duel two planets by size, take the diameter quiz, find your planet birthdays, "
        "then see all eight on one scale or as a bar graph."
    )


def test_header_holds_only_title_and_tagline_with_one_link(client):
    header, _ = _markup(client)
    tags = re.findall(r"<(\w+)\b([^>]*)>", unescape(header))
    assert tags == [("h1", ' data-marker="solar-arcade"'), ("p", ' class="tagline"'), ("a", ' href="#scale-title"')]
    assert ">Solar Arcade</h1>" in header


def test_tagline_is_one_sentence_of_at_most_three_lines_on_a_phone(client):
    # Measured on the words a visitor reads, not the link markup around them.
    text = _text(_markup(client)[1])
    assert len(re.findall(r"[.!?]", text)) == 1 and text[-1] in ".!?"
    assert _lines(text, VIEWPORT - 2 * BODY_PAD) <= 3


HARNESS = r"""
const vm = require("vm");
const fs = require("fs");
const input = JSON.parse(fs.readFileSync(0, "utf8"));
const html = input.page;
const radios = ["scale-view-circles", "scale-view-bars"];
const elements = {};
for (const [, id] of html.matchAll(/\bid="([\w-]+)"/g)) {
  const tagAt = html.lastIndexOf("<", html.indexOf('id="' + id + '"'));
  const open = html.slice(tagAt, html.indexOf(">", tagAt) + 1);
  elements[id] = { id, checked: /\bchecked\b/.test(open), closest: () => null, scrollIntoView() {} };
}
for (const id of radios) {
  const el = elements[id];
  let checked = el.checked;
  Object.defineProperty(el, "checked", {
    get: () => checked,
    set(v) { checked = v; if (v) for (const other of radios) if (other !== id) elements[other].checked = false; },
  });
}
const listeners = {};
const log = { prevented: [], fetched: [] };
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

for (const step of input.steps) {
  if (step.do === "pick") { elements[step.id].checked = true; continue; }
  const url = new URL(step.href, win.location.href);
  const inside = step.in === "tagline" ? [".tagline", "header"] : [step.in === "nav" ? ".section-nav" : ""];
  const link = {
    href: url.href, hash: url.hash, pathname: url.pathname, origin: url.origin, target: "",
    closest(sel) { return sel === "a[href]" || inside.includes(sel) ? this : null; },
    matches(sel) { return inside.some((s) => s && sel.includes(s)); },
  };
  const event = { type: "click", button: 0, target: link, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; } };
  for (const fn of listeners.click || []) fn(event);
  log.prevented.push(event.defaultPrevented);
}
log.bars = elements["scale-view-bars"].checked;
log.circles = elements["scale-view-circles"].checked;
process.stdout.write(JSON.stringify(log));
"""


def _run(client, steps):
    node = shutil.which("node")
    if node is None:
        pytest.fail("node is needed to run the home page script")
    payload = {"base": BASE, "script": str(SCRIPT), "page": client.get("/").text, "steps": steps}
    out = subprocess.run(
        [node, "-e", HARNESS], input=json.dumps(payload), capture_output=True, text=True, timeout=30, check=False
    )
    assert out.returncode == 0, out.stderr
    return json.loads(out.stdout)


def test_tagline_bar_graph_link_picks_bar_graph_and_lets_the_jump_happen(client):
    log = _run(client, [{"do": "click", "href": "#scale-title", "in": "tagline"}])
    assert log["bars"] is True and log["circles"] is False
    # Not prevented: the browser's own fragment jump scrolls to the chart (and does so without the script).
    assert log["prevented"] == [False]
    assert log["fetched"] == []


def test_tagline_bar_graph_link_keeps_bar_graph_when_already_picked(client):
    log = _run(client, [{"do": "pick", "id": "scale-view-bars"}, {"do": "click", "href": "#scale-title", "in": "tagline"}])
    assert log["bars"] is True and log["circles"] is False
    assert log["prevented"] == [False]


def test_scale_nav_link_does_not_switch_the_view(client):
    log = _run(client, [{"do": "click", "href": "#scale-title", "in": "nav"}])
    assert log["circles"] is True and log["bars"] is False
    assert log["prevented"] == [False]
