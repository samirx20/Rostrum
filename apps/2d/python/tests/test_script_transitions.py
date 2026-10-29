"""transition() and carry() (script_transitions.py): each kind writes plain keys / masks / effects on both sections,
a carried layer keeps showing past its section's end and lands on `to`, and a re-run leaves the same document."""
import copy

import pytest
from rostrum_core import Who
from rostrum_core.mcp import Runtime

from rostrum2d.evaluate import value_at
from rostrum2d.mcp import app_tools, make_app
from rostrum2d.script import run_source

AGENT = Who.agent("tester")
SECTIONS = '''comp("main", width=640, height=360, fps=30, duration=4)
with group("a", w=640, h=360) as a:
    shape("bg_a", w=640, h=360, x=320, y=180, fill="#203060")
    shape("logo", shape="ellipse", w=80, h=80, x=320, y=180, fill="#ffcc00")
with group("b", w=640, h=360) as b:
    shape("bg_b", w=640, h=360, x=320, y=180, fill="#c04030")
'''


def built(line):
    root = run_source(SECTIONS + line, "t.py")
    return {n["id"]: n for n in _walk(root)}


def _walk(n):
    for v in n.values():
        if isinstance(v, list):
            for c in v:
                if isinstance(c, dict):
                    yield c
                    yield from _walk(c)


def props(node):
    return {k["prop"] for k in node.get("keys", [])}


@pytest.mark.parametrize("kind, on_a, on_b", [
    ("cut", set(), set()), ("fade", {"opacity"}, {"opacity"}), ("push", {"x"}, {"x"}), ("slide", set(), {"x"}),
    ("wipe", set(), set()), ("iris", set(), set()), ("zoom", {"scale", "opacity"}, {"scale", "opacity"}),
    ("blur", {"opacity"}, {"opacity"})])
def test_each_kind_writes_keys_on_both_sections(kind, on_a, on_b):
    n = built(f'transition("{kind}", at=1, dur=0.5, out_of=a, into="b")')
    a, b = n["a"], n["b"]
    assert props(a) == on_a and props(b) == on_b
    assert b["start"] == 1 and a["end"] == (1 if kind == "cut" else 1.5)
    if kind == "push":            # out_of leaves by one view width, into arrives from one view width away
        assert value_at(a, "x", 1.5) - value_at(a, "x", 1) == -640 and value_at(b, "x", 1) - value_at(b, "x", 1.5) == 640
    if kind in ("wipe", "iris"):
        m = n[f"b_{kind}"]
        assert m["type"] == "mask" and value_at(m, "w", 1) == 0 and value_at(m, "w", 1.5) >= 640
    if kind == "blur":
        assert value_at(n["a_out_blur"], "radius", 1.5) == 40 and value_at(n["b_in_blur"], "radius", 1.5) == 0


def test_a_wrong_kind_or_parameter_is_named():
    for line, words in (('transition("spin", out_of=a, into=b)', "kinds are"),
                        ('transition("push", out_of=a, into=b, softness=3)', 'no "softness"'),
                        ('transition("wipe", out_of=a, into=b, direction="sideways")', "directions are")):
        with pytest.raises(Exception, match=words):
            built(line)


def test_carry_keeps_the_layer_past_its_section_and_lands_on_to():
    n = built('transition("push", at=1, dur=0.5, out_of=a, into=b)\n'
              'carry("logo", into=b, at=1, dur=0.5, to=dict(x=60, y=40, scale=0.5))')
    logo, twin = n["logo"], n["logo_carry"]
    assert logo["end"] == 1 and twin["start"] == 1 and twin["end"] > 1.5
    assert (value_at(twin, "x", 1), value_at(twin, "y", 1)) == (320, 180)       # where it showed
    assert (value_at(twin, "x", 1.5), value_at(twin, "y", 1.5), value_at(twin, "scale", 1.5)) == (60, 40, 0.5)


def test_a_rerun_gives_the_same_document(tmp_path):
    rt = Runtime(make_app(str(tmp_path), ["demo"]), app_tools())
    src = SECTIONS + ('transition("wipe", at=1, dur=0.5, out_of=a, into=b, softness=20)\n'
                      'carry("logo", into=b, at=1, dur=0.5, to=dict(scale=3))')
    docs = []
    for _ in range(2):
        reply, _ = rt.call("run_script", {"source": src, "name": "t.py"}, AGENT)
        assert reply["ok"], reply["summary"]
        docs.append(copy.deepcopy(next(iter(rt.app.documents.values())).data))
    assert docs[0] == docs[1]
