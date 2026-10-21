"""Painted backgrounds: background.move keeps every stroke where it sits in the composition, and is one undo step."""
import copy

from rostrum_core import Document, Who

from rostrum2d import KIND, run_source
from rostrum2d import background as B

AGENT = Who.agent("tester")
SETUP = 'comp("c", fps=10, duration=2)\ncam = camera("cam")\ncam.key("x", {0: 700, 2: 1200})\n'


def test_move_keeps_every_stroke_in_place_and_is_one_undo_step():
    d = Document.new(KIND)
    d.run_script("s.py", run_source(SETUP, "s.py"))
    d.apply({"op": "background.add", "target": "c", "args": {"depths": [2.0, 0.5]}}, AGENT)
    far, near = (l for l in d.item("c")["layers"] if l["type"] == "drawing")
    paint = near["frames"][0]["paints"][0]["id"]
    d.apply([{"op": "stroke.add", "target": paint, "args": {"points": [[100 + 40 * i, 300], [400, 360 + i]], "size": 20}} for i in range(5)], AGENT)
    before = {s["id"]: [B.to_comp(d.item(near["id"]), *p[:2]) for p in s["points"]] for s in d.item(paint)["strokes"]}
    snapshot = copy.deepcopy(d.data)
    d.apply({"op": "background.move", "target": [paint], "args": {"into": far["id"]}}, AGENT)
    moved = {s["id"]: [B.to_comp(d.item(far["id"]), *p[:2]) for p in s["points"]] for s in d.item(paint)["strokes"]}
    assert moved.keys() == before.keys()
    assert all(abs(a - b) < 0.01 for k in before for p, q in zip(before[k], moved[k]) for a, b in zip(p, q))
    assert d.parent_of(paint)[0] == far["frames"][0]["id"]
    d.undo(AGENT)
    assert d.data == snapshot
