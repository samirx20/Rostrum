"""A painted fill as the engine reads it (painted_fill.py, scene.py): layers sharing a painting name the same picture files
(one per drawing, not per layer), a painting that draws each frame always loops from the layer's own start, and a colour
under it that is not set goes as no colour."""
import copy

import pytest
from rostrum_core import Document, Who

from rostrum2d import KIND, scene

SAM = Who.person("sam")


def stroke(i):
    return {"points": [[4, 4], [30 + i * 10, 40]], "size": 12, "color": "#ff0000", "hardness": 1.0, "space": "canvas"}


def build():
    """A document whose painting "boil" has three different drawings (at 0, 2, 4), each from a stroke of its own."""
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film", "fps": 10, "duration": 3}},
             *({"op": "painting.add", "args": {"id": f"p{i}", "w": 64, "h": 64}} for i in range(3)),
             *({"op": "layer.add", "target": "film", "args": {"type": "shape", "id": i}} for i in "abc")], SAM)
    for i in range(3):
        d.apply({"op": "paint.stroke", "target": f"p{i}", "args": stroke(i)}, SAM)
    data = copy.deepcopy(d.data)
    frames = [{**data["paintings"][i]["frames"][0], "id": f"f{i}", "at": i * 2} for i in range(3)]
    data["paintings"] = [{**data["paintings"][0], "id": "boil", "frames": frames, "eachFrame": True}]
    for i in "abc":
        layer = next(l for l in data["comps"][0]["layers"] if l["id"] == i)
        layer.update(fillType="painted", fillPainting="boil", filled=True)
        if i == "b":
            layer.update(start=1.0, fillPhase=1)
    return data


def test_painted_fill_frames():
    data = build()
    nodes = {n["id"]: n for n in scene.describe(data, "film")["comp"]["layers"]}
    a, b, c = (nodes[i] for i in "abc")
    assert a["props"]["fillPicture"] == "" and a["props"]["fillUnder"] == "#00000000"
    assert [f["src"] for f in a["fillFrames"]] == [f["src"] for f in c["fillFrames"]][:len(a["fillFrames"])]   # one picture per drawing
    files = [f["src"] for f in a["fillFrames"][:3]]
    assert len(set(files)) == 3
    ids = {f: i for i, f in enumerate(files)}
    assert [(f["at"], ids[f["src"]]) for f in b["fillFrames"][:4]] == [(10, 1), (12, 2), (14, 0), (16, 1)]   # starts at 1 s on drawing 1


def test_a_colour_under_it_that_is_not_set_goes_as_none_and_a_missing_painting_fails_loudly():
    data = build()
    layer = next(l for l in data["comps"][0]["layers"] if l["id"] == "c")
    layer.update(fillUnder="#0000ff", fillType="solid")                  # chosen once, then left for a colour fill
    assert next(n for n in scene.describe(data, "film")["comp"]["layers"] if n["id"] == "c")["props"]["fillUnder"] == "#00000000"
    layer.update(fillType="painted", fillPainting="gone")
    with pytest.raises(ValueError, match="c: .*gone"):
        scene.describe(data, "film")
