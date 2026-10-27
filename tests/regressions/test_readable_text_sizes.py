import itertools
import re

MIN_REM = 0.875  # 14px at the 16px body size
REM = 16  # px, body font-size
LINE_HEIGHT = 1.2  # .inset-label line-height
# 390px phone: minus body padding (2 x 16px) and the panel's padding + border (2 x 17px).
PHONE_FRAME = 390 - 32 - 34
INSET_ROW = re.compile(r'<li class="inset-row"[^>]*>(.*?)</li>', re.DOTALL)


def _css(client):
    return client.get("/static/arcade.css").text


def _rules(css, selector):
    return " ".join(re.findall(re.escape(selector) + r"\s*(?:,[^{]*)?\{([^}]*)\}", css))


def _hex(css, name):
    return re.search(r":root\s*\{[^}]*" + re.escape(name) + r":\s*#([0-9a-fA-F]{6})", css).group(1)


def _luminance(hex6):
    def channel(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (channel(int(hex6[i:i + 2], 16)) for i in (0, 2, 4))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    hi, lo = sorted((_luminance(a), _luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_no_font_size_below_14px_outside_a_min_cap(client):
    css = _css(client)
    sizes = re.findall(r"font-size:\s*([^;}]+)", css)
    assert len(sizes) > 20
    small = []
    for value in sizes:
        bare = re.sub(r"min\([^)]*\)", "", value)  # a min() cap may go lower so leader labels never overlap
        small += [value for n in re.findall(r"([\d.]+)rem", bare) if float(n) < MIN_REM]
        small += [value for n in re.findall(r"([\d.]+)px", bare) if float(n) < MIN_REM * REM]
    assert not small, small


def test_leader_cap_starts_at_14px(client):
    leader = _rules(_css(client), ".scale-label--leader")
    assert re.search(r"font-size:\s*min\(0\.875rem,\s*5cqi\)", leader), leader


def test_named_captions_are_at_least_14px(client):
    css = _css(client)
    phone = re.search(r"@media\s*\(max-width:\s*420px\)\s*\{(.*?)\n\}", css, re.DOTALL).group(1)
    for selector, body in [(".planet-card .order", css), (".planet-card .label", css),
                           (".planet-card .earths", css), (".planet-card .earths", phone),
                           (".scale-label", css), (".inset-label", css),
                           (".quiz-pick", css), (".quiz-larger", css)]:
        size = re.findall(r"font-size:\s*([\d.]+)rem", _rules(body, selector))
        assert size and float(size[-1]) >= MIN_REM, (selector, size)


def test_muted_is_lighter_with_6_to_1_on_navy(client):
    css = _css(client)
    muted, navy = _hex(css, "--muted"), _hex(css, "--navy")
    assert _luminance(muted) > _luminance("8e98b3")
    assert _contrast(muted, navy) >= 6.0, f"{_contrast(muted, navy):.2f}:1"
    for panel in ("101b40", "13204a"):  # rocky inset / chart panel, quiz and card panel
        assert _contrast(muted, panel) >= 6.0, panel


def test_rocky_inset_labels_at_new_size_do_not_overlap_at_390px(client):
    css = _css(client)
    rem = float(re.search(r"font-size:\s*([\d.]+)rem", _rules(css, ".inset-label")).group(1))
    assert rem >= MIN_REM
    label_pct = 2 * LINE_HEIGHT * rem * REM / PHONE_FRAME * 100  # name + value lines
    spans = []
    for body in INSET_ROW.findall(client.get("/").text):
        name = re.search(r'class="inset-name"[^>]*>([^<]*)<', body).group(1)
        mode, y = re.search(r'class="inset-label inset-label--(\w+)"[^>]*style="--y:\s*([\d.]+)%', body).groups()
        assert mode in ("inside", "above"), name
        top = 100 - float(y) + 4 if mode == "inside" else 100 - float(y) - 1 - label_pct
        spans.append((top, top + label_pct, name))
    assert len(spans) == 4
    spans.sort()
    for (_, end, a), (start, _, b) in itertools.pairwise(spans):
        assert end <= start, f"{a} label overlaps {b}"
