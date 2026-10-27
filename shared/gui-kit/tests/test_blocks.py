"""The block view's rules: a wire that closes a loop or joins the wrong kinds is refused; the add list finds a type by
its name first; and the view's own copy of the rules (Blocks.js, which lights the ports while wiring) says the same
as rostrum_gui/blocks.py (which the app checks before it wires). A drift would light a port the app then refuses."""
import json
from pathlib import Path

import pytest

from rostrum_gui import blocks

N, C = "number", "colour"
CONVERTS = {N: [C], C: [N]}


def block(bid, ins=(), outs=(), x=0, y=0, summary=""):
    return {"id": bid, "x": x, "y": y, "summary": summary,
            "inputs": [{"name": n, "kind": k} for n, k in ins], "outputs": [{"name": n, "kind": k} for n, k in outs]}


BLOCKS = [block("a", [("in", N)], [("out", N), ("col", C)]), block("b", [("in", N), ("c", C)], [("out", N)]),
          block("c", [("in", N), ("n", "normal")], [("out", N), ("st", "style")]), block("d", [("in", N)], [("out", N)])]
WIRES = [{"from": "a.out", "to": "b.in"}, {"from": "b.out", "to": "c.in"}]
CATALOGUE = [
    {"type": "noise", "label": "Noise", "group": "Patterns", "words": "random cloud", "inputs": [{"name": "s", "kind": N}]},
    {"type": "mix", "label": "Mix", "group": "Colour", "words": "blend multiply", "inputs": [{"name": "a", "kind": C}]},
    {"type": "adjust", "label": "Colour adjust", "group": "Colour", "words": "saturation",
     "inputs": [{"name": "c", "kind": C}]},
    {"type": "bevel", "label": "Bevel shading", "group": "Shape", "words": "", "inputs": [{"name": "r", "kind": "normal"}]},
    {"type": "image", "label": "Image", "group": "Patterns", "words": "picture", "inputs": []},
]


def test_loops_and_kinds_are_refused():
    r = lambda f, t: blocks.refusal(BLOCKS, WIRES, f, t, CONVERTS)  # noqa: E731
    assert r("c.out", "a.in") == "loop"           # c is fed by b, b by a: a <- c closes a loop
    assert r("b.out", "a.in") == "loop"
    assert r("a.out", "a.in") == "same-block"
    assert r("c.st", "d.in") == "kind"            # a style feeds only a style
    assert r("a.out", "c.n") == "kind"            # a number never feeds a normal
    assert r("a.col", "d.in") == ""               # a colour feeds a number (its brightness)
    assert r("a.out", "b.c") == ""                # ... and a number a colour
    assert r("a.out", "x.in") == "unknown" and r("a.nope", "d.in") == "unknown"
    # one wire per input: wiring c into b.in replaces a -> b.in, so the old path a -> b no longer counts
    assert blocks.makes_loop(WIRES, "c", "b", "b.in") is True    # b -> c -> b.in still loops through b itself
    assert blocks.makes_loop(WIRES, "c", "a", "") is True
    assert blocks.makes_loop([{"from": "a.out", "to": "b.in"}], "b", "a", "") is True
    assert blocks.makes_loop([{"from": "a.out", "to": "b.in"}], "d", "a", "") is False


def test_search_puts_the_name_first_and_follows_a_dropped_wire():
    names = lambda q, kind="": [e["type"] for e in blocks.search(CATALOGUE, q, kind, CONVERTS)]  # noqa: E731
    assert names("") == ["noise", "mix", "adjust", "bevel", "image"]
    assert names("co") == ["adjust", "mix"]         # the label starts with it, then a group "Colour" match
    assert names("adj col") == ["adjust"]           # every word starts a word, any order
    assert names("sat") == ["adjust"]               # the type's own words
    assert names("ix") == []                        # word starts only: "ix" is not "Mix"
    assert names("", "normal") == ["bevel"]         # a dropped normal wire: only what takes a normal
    assert names("", N) == ["noise", "mix", "adjust"]   # a number also feeds a colour; Image takes nothing
    assert blocks.first_input(CATALOGUE[1], N, CONVERTS) == "a"


def _js():
    from PySide6.QtQml import QJSEngine
    eng = QJSEngine()
    src = (Path(blocks.__file__).resolve().parents[1] / "qml" / "RostrumKit" / "Blocks.js").read_text(encoding="utf-8")
    eng.evaluate(src.replace(".pragma library", ""))
    return eng


def _call(eng, expr):
    v = eng.evaluate(f"JSON.stringify({expr})")
    assert not v.isError(), v.toString()
    return json.loads(v.toString())


@pytest.mark.parametrize("q,kind", [("", ""), ("co", ""), ("adj col", ""), ("sat", ""), ("ix", ""), ("", "normal"),
                                    ("", N), ("s", C), ("bevel  SHA", "")])
def test_the_view_searches_like_python(q, kind):
    eng = _js()
    js = _call(eng, f"search({json.dumps(CATALOGUE)}, {json.dumps(q)}, {json.dumps(kind)}, {json.dumps(CONVERTS)})")
    assert [e["type"] for e in js] == [e["type"] for e in blocks.search(CATALOGUE, q, kind, CONVERTS)]


def test_the_view_wires_and_lays_out_like_python():
    eng = _js()
    w, cv = json.dumps(WIRES), json.dumps(CONVERTS)
    for f, t in [("c", "a"), ("b", "a"), ("d", "a"), ("a", "d"), ("c", "b")]:
        for port in ("", f"{t}.in"):
            assert _call(eng, f"makesLoop({w}, '{f}', '{t}', '{port}')") == blocks.makes_loop(WIRES, f, t, port)
    for o in (N, C, "normal", "style"):
        for i in (N, C, "normal", "style"):
            assert _call(eng, f"compatible('{o}', '{i}', {cv})") == blocks.compatible(o, i, CONVERTS)
    for b in BLOCKS + [block("s", [("x", N)], [("y", C)], 40, 60, summary="Scale 8")]:
        assert _call(eng, f"height({json.dumps(b)})") == blocks.height(b)
        for side, ports in (("out", b["outputs"]), ("in", b["inputs"])):
            for p in ports:
                js = _call(eng, f"portAt({json.dumps(b)}, '{side}', '{p['name']}')")
                assert (b["x"] + js["x"], b["y"] + js["y"]) == blocks.port_at(b, side, p["name"])
