"""Script errors say what was passed and what is accepted (the runner adds the line); the camera note says what the camera did."""
import pytest
from rostrum_core import RostrumError

from rostrum2d.mcp import review_facts
from rostrum2d.script import run_source

HEAD = 'comp("main", duration=10)\n'


def _fails(body):
    with pytest.raises(RostrumError) as e:
        run_source(HEAD + body, "film.py")
    return str(e.value)


def _ids(node):
    if isinstance(node, dict):
        yield from ([node["id"]] if isinstance(node.get("id"), str) else [])
        for v in node.values():
            yield from _ids(v)
    elif isinstance(node, list):
        for v in node:
            yield from _ids(v)


def test_math_text_with_a_vertical_bar_typesets_it_as_a_symbol():
    root = run_source(HEAD + 'eq = math_text("eq", r"|x|")\n', "film.py")
    ids = sorted(i for i in _ids(root) if i.startswith("eq_"))
    assert ids == ["eq_1_bar", "eq_2_x", "eq_3_bar"], ids       # the glyph "|" is named bar like a rule, and both draw


def test_stagger_given_pairs_names_the_pair_and_what_it_takes():
    msg = _fails('a = text("a", body="A")\nb = text("b", body="B")\nfor t, it in stagger(stagger([a, b], every=0.2)):\n    pass\n')
    assert "line 4" in msg and "(time, item) pair" in msg and "stagger([a, b, c]" in msg, msg


def test_stagger_every_must_be_a_number():
    msg = _fails('stagger([], every="slow")\n')
    assert "every='slow'" in msg and "seconds" in msg and "line 2" in msg, msg


def _comp(key):
    root = run_source(HEAD + key, "film.py")
    return root["comps"][0]


def test_a_drifting_camera_is_reported_with_its_travel_not_as_never_changing():
    comp = _comp('f = frame()\nf.key("x", {0: 960, 66: 1000}, ease="linear")\n')
    comp.setdefault("width", 1920)
    times = [float(t) for t in range(0, 10)]
    for fault in review_facts.framing(comp, times, 1.0):
        assert "never changes" not in fault["text"], fault
        assert fault["camera_px"] > 0 and "drifts" in fault["text"] and "no cut" in fault["text"], fault


def test_a_camera_that_never_moves_still_says_so():
    comp = _comp('f = frame()\n')
    faults = review_facts.framing(comp, [float(t) for t in range(0, 12)], 1.0)
    assert faults and "never changes" in faults[0]["text"] and faults[0]["camera_px"] == 0
