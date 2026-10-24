"""#56: when taps overlap and their responses come back out of order, the latest interaction stays on screen.

Reuses the Node harness from test_controls_run_in_place.py and adds two steps: answer one pending fetch by
its position, and go back (popstate) to a URL.
"""
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "controls_run_in_place", Path(__file__).with_name("test_controls_run_in_place.py")
)
_base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_base)
BASE, SCRIPT, text = _base.BASE, _base.SCRIPT, _base.text

_HOOK = '    } else if (step.do === "respond") {'
assert _HOOK in _base.HARNESS
HARNESS = _base.HARNESS.replace(_HOOK, """    } else if (step.do === "respondTo") {
      // Answer the pending fetch for one path, leaving the others waiting.
      const waiting = log.fetched.filter((p) => !p.startsWith("answered:"));
      pending.splice(waiting.indexOf(step.path), 1)[0]();
      log.fetched[log.fetched.indexOf(step.path)] = "answered:" + step.path;
      await settle();
    } else if (step.do === "back") {
      win.location.href = input.base + step.to;
      for (const fn of listeners["window:popstate"] || []) fn({ type: "popstate" });
""" + _HOOK, 1)


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


JUPITER = "/?round=1&choice=jupiter"
EARTH = "/?round=1&choice=earth"


def test_earlier_quiz_answer_arriving_last_does_not_overwrite_the_latest(client):
    log = run(client, [
        {"do": "scrollTo", "y": 400},
        {"do": "submit", "region": "planet-quiz", "fields": [["round", "1"]], "submitter": ["choice", "jupiter"]},
        {"do": "submit", "region": "planet-quiz", "fields": [["round", "1"]], "submitter": ["choice", "earth"]},
        {"do": "respondTo", "path": EARTH},
        {"do": "respondTo", "path": JUPITER},
    ], [JUPITER, EARTH])
    quiz = text(log["regions"]["planet-quiz"])
    assert "You chose Earth." in quiz
    assert "Correct" not in quiz
    assert log["pushed"] == [BASE + EARTH]
    assert log["navigated"] == []


def test_latest_quiz_answer_still_shows_when_responses_arrive_in_order(client):
    log = run(client, [
        {"do": "submit", "region": "planet-quiz", "fields": [["round", "1"]], "submitter": ["choice", "jupiter"]},
        {"do": "submit", "region": "planet-quiz", "fields": [["round", "1"]], "submitter": ["choice", "earth"]},
        {"do": "respondTo", "path": JUPITER},
        {"do": "respondTo", "path": EARTH},
    ], [JUPITER, EARTH])
    assert "You chose Earth." in text(log["regions"]["planet-quiz"])
    assert log["pushed"][-1] == BASE + EARTH


def test_superseded_request_failing_does_not_reload_the_page(client):
    log = run(client, [
        {"do": "click", "region": "birthday-booth", "href": "/?age=10"},
        {"do": "submit", "region": "planet-quiz", "fields": [["round", "1"]], "submitter": ["choice", "earth"]},
        {"do": "respondTo", "path": EARTH},
        {"do": "respondTo", "path": "/?age=10"},
    ], [EARTH])
    assert log["navigated"] == []
    assert "You chose Earth." in text(log["regions"]["planet-quiz"])
    assert log["pushed"] == [BASE + EARTH]


def test_going_back_supersedes_a_pending_tap(client):
    log = run(client, [
        {"do": "click", "region": "planet-quiz", "href": "/?round=2"},
        {"do": "back", "to": "/"},
        {"do": "respondTo", "path": "/"},
        {"do": "respondTo", "path": "/?round=2"},
    ], ["/?round=2", "/"])
    quiz = text(log["regions"]["planet-quiz"])
    assert "Round 1 of 3" in quiz
    assert "Round 2 of 3" not in quiz
    assert log["pushed"] == []
    assert log["navigated"] == []
