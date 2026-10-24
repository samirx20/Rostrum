"""A layer's drawings share its paint layers (shared_paints.py, rostrum_paint.linked): an edit on one drawing's paint
layer reaches every drawing in one undo step, New and Copy keep the layers, and an older file whose drawings each had
their own paint layers opens lined up to the same pixels."""
import copy

from rostrum_core import Document, Who
from rostrum_paint import canvas

from rostrum2d import KIND
from rostrum2d.kind import upgrade

SAM = Who.person("sam")
LINE = {"points": [[10, 10], [90, 90]], "space": "canvas"}


def drawn() -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             {"op": "layer.add", "target": "film", "args": {"type": "drawing", "id": "fire"}},
             {"op": "drawing.set", "target": "fire", "args": {"w": 100, "h": 100, "eachFrame": True}}], SAM)
    d.apply({"op": "paint.stroke", "target": "fire", "args": LINE}, SAM)
    d.apply({"op": "frame.add", "target": "fire", "args": {"id": "f2"}}, SAM)
    return d


def layers(d):
    return [[(p["name"], p.get("layer") or p["id"], p["locked"], len(p["strokes"])) for p in f["paints"]]
            for f in d.item("fire")["frames"]]


def test_an_edit_reaches_every_drawing_in_one_step():
    d = drawn()
    d.apply({"op": "paint.add", "target": "f2", "args": {"name": "Colour", "index": 0}}, SAM)
    colour = d.item("f2")["paints"][0]["id"]
    d.apply({"op": "frame.add", "target": "fire", "args": {"id": "f3", "copy": "f2"}}, SAM)
    d.apply({"op": "paint.stroke", "target": "fire", "args": {**LINE, "frame": 4, "layer": colour}}, SAM)
    d.apply({"op": "paint.set", "target": d.item("fire")["frames"][0]["paints"][1]["id"], "args": {"locked": True}}, SAM)
    keys = [[k for _, k, _, _ in f] for f in layers(d)]
    assert keys[0] == keys[1] == keys[2] and len(keys[0]) == 2
    assert [f[1][2] for f in layers(d)] == [True, True, True]          # Paint locked everywhere
    assert [f[0][3] for f in layers(d)] == [0, 0, 1]                    # each drawing its own Colour strokes
    d.undo(SAM)
    assert [f[1][2] for f in layers(d)] == [False, False, False]
    d.apply({"op": "paint.move", "target": colour, "args": {"index": 1}}, SAM)
    assert [f[1][0] for f in layers(d)] == ["Colour"] * 3


def test_drift_between_drawings_is_refused():
    d = drawn()
    data = copy.deepcopy(d.data)
    data["comps"][0]["layers"][1]["frames"][1]["paints"][0]["opacity"] = 0.5
    assert any("same paint layers" in p for p in KIND.problems(data))


def test_an_older_file_opens_lined_up_to_the_same_pixels():
    d = drawn()
    old = copy.deepcopy(d.data)
    frames = old["comps"][0]["layers"][1]["frames"]
    ink = copy.deepcopy(frames[0]["paints"][0])                         # the old way: each drawing its own layers
    frames[1]["paints"] = [{**ink, "id": "paint_9", "strokes": [{**ink["strokes"][0], "id": "stroke_9"}]},
                           {**ink, "id": "paint_10", "name": "Shade", "strokes": [{**ink["strokes"][0], "id": "stroke_10"}]}]
    assert KIND.problems(old)
    before = [canvas.rgba8(f, 100, 100).tobytes() for f in frames]
    new, label = upgrade(old, KIND.lists)
    assert not KIND.problems(new) and "shared" in label
    got = new["comps"][0]["layers"][1]["frames"]
    assert [p["name"] for p in got[0]["paints"]] == [p["name"] for p in got[1]["paints"]] == ["Ink", "Shade"]
    assert [canvas.rgba8(f, 100, 100).tobytes() for f in got] == before
    assert upgrade(new, KIND.lists) is None
