"""Paintings (paintings.py, ops_painting.py): what people and agents rely on. Each action is one undo step that takes back
everything it did; deleting a painting that layers use never leaves them pointing at nothing (and undo brings it all back);
an older file gets the paintings list; a script re-run keeps a person's stroke in a painting."""
import json

import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_core.storage import paths

from rostrum2d import KIND, run_source

SAM = Who.person("sam")
STROKE = {"points": [[4, 4], [60, 60]], "size": 20, "color": "#ff0000", "hardness": 1.0, "space": "canvas"}


def scene() -> Document:
    d = Document.new(KIND)
    d.apply([{"op": "comp.add", "args": {"id": "film"}},
             *({"op": "layer.add", "target": "film", "args": {"type": "shape", "id": i}} for i in ("card", "tag")),
             {"op": "shape.set", "target": "card", "args": {"w": 200, "h": 100, "fill": "#0000ff"}}], SAM)
    return d


def test_make_painted_fill_moves_the_paint_in_one_undo_step():
    d = scene()
    d.apply({"op": "paint.stroke", "target": "card", "args": {**STROKE, "space": "canvas"}}, SAM)
    before = json.dumps(d.data, sort_keys=True)
    d.apply({"op": "painting.add", "args": {"from": "card", "onto": ["tag"]}}, SAM)
    card, tag, [p] = d.item("card"), d.item("tag"), d.data["paintings"]
    assert (p["w"], p["h"]) == (200, 100) and p["frames"][0]["paints"][0]["strokes"]       # the paint moved into the painting
    assert not card["frames"] and not card["paintW"]
    assert (card["fillType"], card["fillPainting"], card["fillUnder"], card["fillFit"]) == ("painted", p["id"], "#0000ff", "stretch")
    assert tag["fillPainting"] == p["id"]                                                   # and one more layer uses it
    d.undo(SAM)
    assert json.dumps(d.data, sort_keys=True) == before                                     # one step took it all back


def test_a_drawing_is_copied_not_moved():
    d = scene()
    d.apply({"op": "layer.add", "target": "film", "args": {"type": "drawing", "id": "scribble"}}, SAM)
    d.apply({"op": "paint.stroke", "target": "scribble", "args": {**STROKE, "space": "canvas"}}, SAM)
    d.apply({"op": "painting.add", "args": {"from": "scribble"}}, SAM)
    assert d.item("scribble")["frames"][0]["paints"][0]["strokes"]                          # the drawing keeps its strokes
    assert d.data["paintings"][0]["frames"][0]["paints"][0]["strokes"]
    assert d.data["paintings"][0]["w"] == 1920


def test_deleting_a_painting_in_use_makes_solid_fills_and_undo_brings_it_back():
    d = scene()
    d.apply({"op": "painting.add", "args": {"w": 64, "h": 64, "onto": ["card", "tag"]}}, SAM)
    pid = d.data["paintings"][0]["id"]
    d.apply({"op": "layer.fill", "target": ["card", "tag"], "args": {"under": ""}}, SAM)    # no colour under: the paint alone
    d.apply({"op": "paint.stroke", "target": pid, "args": STROKE}, SAM)
    before = json.dumps(d.data, sort_keys=True)
    d.apply({"op": "painting.remove", "target": pid}, SAM)
    assert not d.data["paintings"]
    for layer in ("card", "tag"):
        item = d.item(layer)
        assert item["fillType"] == "solid" and item["fillPainting"] == "" and item["fill"][1:3] > "c0"   # the red it was painted with
    assert KIND.check(d.data) == []                                                         # nothing points at nothing
    d.undo(SAM)
    assert json.dumps(d.data, sort_keys=True) == before


def test_a_painted_fill_naming_a_missing_painting_is_refused_loudly():
    d = scene()
    with pytest.raises(RostrumError, match="painting_9"):
        d.apply({"op": "layer.fill", "target": "card", "args": {"type": "painted", "painting": "painting_9"}}, SAM)
    d.apply({"op": "painting.add", "args": {"onto": ["card"]}}, SAM)
    with pytest.raises(RostrumError, match="tile"):                                        # drift needs Tile
        d.apply({"op": "layer.fill", "target": "card", "args": {"driftX": 10}}, SAM)
    d.apply({"op": "layer.fill", "target": "card", "args": {"fit": "tile", "driftX": 10, "under": "#ffffff"}}, SAM)
    assert d.item("card")["fillDriftX"] == 10 and d.item("card")["fillUnder"] == "#ffffff"


def test_a_format_3_file_opens_with_its_paintings_list(tmp_path):
    d = scene()
    d.folder, d.item_id = tmp_path, "film"
    d.save()
    p = paths(tmp_path, "film", KIND.ext)
    file = json.loads(p["doc"].read_text(encoding="utf-8"))
    file["version"] = 3
    file["doc"].pop("paintings", None)
    p["doc"].write_text(json.dumps(file), encoding="utf-8")
    p["history"].unlink()
    d = Document.open(tmp_path, "film", KIND)
    assert d.data["paintings"] == [] and "Paintings list" in d.history.changes[-1].label


def test_a_script_rerun_keeps_a_persons_stroke_in_the_painting():
    source = ('comp("film")\ngrain = painting("grain", w=64, h=64, seamless=True)\n'
              'shape("card", w=200, h=100, fill=painted(grain, fit="tile", drift=(12, 0)))\n')
    d = Document.new(KIND)
    d.run_script("a.py", run_source(source, "a.py"))
    assert d.item("grain")["seamless"] and d.item("card")["fillPainting"] == "grain"
    d.apply({"op": "paint.stroke", "target": "grain", "args": STROKE}, SAM)
    d.apply({"op": "layer.fill", "target": "card", "args": {"scale": 0.5}}, SAM)
    d.run_script("a.py", run_source(source, "a.py"))
    assert d.item("grain")["frames"][0]["paints"][0]["strokes"]
    assert d.item("card")["fillScale"] == 0.5


def test_a_layer_given_a_painting_keeps_its_colour_under_it():
    """New painted fill (the picker's 2 clicks) and picking an existing painting leave the layer looking as it did: its
    solid colour becomes the colour under the (blank) painting. One undo step takes the new one back whole."""
    d = scene()
    before = json.dumps(d.data, sort_keys=True)
    d.apply({"op": "painting.add", "args": {"onto": ["card"]}}, SAM)
    [p] = d.data["paintings"]
    assert (d.item("card")["fillType"], d.item("card")["fillUnder"]) == ("painted", "#0000ff")
    d.apply({"op": "shape.set", "target": "tag", "args": {"fill": "#00ff00"}}, SAM)
    d.apply({"op": "layer.fill", "target": "tag", "args": {"type": "painted", "painting": p["id"]}}, SAM)
    assert d.item("tag")["fillUnder"] == "#00ff00"
    d.undo(SAM), d.undo(SAM), d.undo(SAM)
    assert json.dumps(d.data, sort_keys=True) == before
