import itertools
import re

SECTION = re.compile(r'<section class="diameter-scale"[^>]*>(.*?)</section>', re.DOTALL)
LEADER = re.compile(r'<svg class="scale-leader".*?<line ([^>]*)>', re.DOTALL)
REM = 16  # px, body font-size
LINE_HEIGHT = 1.2  # .scale-label line-height
# Narrow phone: 320px viewport minus body padding (2 x 16px) and the section's padding + border (2 x 17px).
NARROW_FRAME = 320 - 32 - 34
WIDE_FRAME = 440


def _rules(css, selector):
    return " ".join(re.findall(r"(?:^|(?<=[}/]))\s*" + re.escape(selector) + r"\s*\{([^}]*)\}", css, re.MULTILINE))


def _leader_ends(client):
    section = SECTION.search(client.get("/").text).group(1)
    return sorted(float(re.search(r'y2="([\d.]+)"', line).group(1)) for line in LEADER.findall(section))


def _label_font_px(css, frame_px):
    """Resolve the leader label font-size: a rem value, optionally capped by a cqi term of the frame."""
    # The leader modifier comes after the base rule, so its font-size (if any) wins.
    decls = re.findall(r"font-size:\s*([^;]+);", _rules(css, ".scale-label") + _rules(css, ".scale-label--leader"))
    value = decls[-1].strip()
    sizes = [float(n) * REM for n in re.findall(r"([\d.]+)rem", value)]
    sizes += [float(n) / 100 * frame_px for n in re.findall(r"([\d.]+)cqi", value)]
    assert sizes, value
    return min(sizes) if value.startswith("min(") or len(sizes) == 1 else max(sizes)


def test_leader_svg_fills_the_circle_frame(client):
    css = client.get("/static/arcade.css").text
    leader = _rules(css, ".scale-leader")
    # A replaced <svg> does not stretch from inset alone; it needs explicit dimensions to match the frame.
    assert re.search(r"(?<![-\w])width:\s*100%", leader), leader
    assert re.search(r"(?<![-\w])height:\s*100%", leader), leader
    assert re.search(r"inset:\s*0", leader)


def test_frame_is_a_size_container_for_label_scaling(client):
    css = client.get("/static/arcade.css").text
    assert re.search(r"container-type:\s*inline-size", _rules(css, ".scale-rows"))


def test_leader_labels_do_not_overlap_on_narrow_or_wide_screens(client):
    css = client.get("/static/arcade.css").text
    ends = _leader_ends(client)
    assert len(ends) == 4
    step = min(b - a for a, b in itertools.pairwise(ends))  # % of the square frame
    for frame in (NARROW_FRAME, WIDE_FRAME):
        label_px = 2 * LINE_HEIGHT * _label_font_px(css, frame)  # name + value lines
        assert step / 100 * frame >= label_px, f"{frame}px frame: {step}% gap < {label_px:.2f}px label"


def test_leader_labels_stay_inside_the_frame(client):
    ends = _leader_ends(client)
    css = client.get("/static/arcade.css").text
    for frame in (NARROW_FRAME, WIDE_FRAME):
        half = LINE_HEIGHT * _label_font_px(css, frame) / frame * 100  # half a label, in % of frame
        assert ends[0] - half >= 0 and ends[-1] + half <= 100
