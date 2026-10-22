"""One step across documents (joint.py + desk.py) and a marker that follows another app's item (links.py): an undo that
took back only half a step, or a cue marker left behind when its layer moved, would break silently."""
import json

import pytest

from rostrum_core import RostrumError, Who, desk, joint, links, live
from rostrum_core import markers as M
from rostrum_core import toy
from rostrum_core.document import Document

SAM, AGENT = Who.person("sam"), Who.agent("claude")


def _project(folder, *items):
    (folder / "project.json").write_text(json.dumps({"items": [{"id": i, "kind": "toy", "name": i} for i in items]}))


def _doc(folder, item):
    d = Document.open(folder, item, toy.KIND) if (folder / "docs" / f"{item}.toy").is_file() else \
        Document(toy.KIND, toy.sample().data, folder, item)
    live.keep(d)
    return d


def test_a_step_across_documents_is_undone_and_redone_whole(tmp_path):
    _project(tmp_path, "scene", "song")
    scene, song = _doc(tmp_path, "scene"), _doc(tmp_path, "song")
    with joint.step():                                   # "Add a sound here": the song and a shared marker
        song.apply([{"op": "layer.rename", "target": ["title"], "args": {"name": "Whoosh"}}], SAM)
        M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "Logo · sound", "at": 1.0}}], SAM)
    marks = M.open_to_change(tmp_path)
    reopened = []
    hit = desk.undo([scene, marks], SAM, open_item=lambda item: reopened.append(item) or _doc(tmp_path, item))
    assert reopened == ["song"] and len(hit.all) == 2
    assert M.listing(tmp_path) == [] and _doc(tmp_path, "song").item("title")["name"] == "Title"

    desk.redo([scene, marks, song], SAM)
    assert [m["name"] for m in M.listing(tmp_path)] == ["Logo · sound"]
    assert _doc(tmp_path, "song").item("title")["name"] == "Whoosh"

    with pytest.raises(RostrumError, match="not open here"):     # never half a step
        desk.undo([scene, M.open_to_change(tmp_path)], SAM)
    assert [m["name"] for m in M.listing(tmp_path)] == ["Logo · sound"]

    song.apply([{"op": "layer.rename", "target": ["title"], "args": {"name": "Swish"}}], AGENT)
    with pytest.raises(RostrumError, match="changed"):            # someone built on it: refused everywhere
        desk.undo([scene, M.open_to_change(tmp_path), song], SAM)
    assert [m["name"] for m in M.listing(tmp_path)] == ["Logo · sound"]


def test_a_marker_follows_its_item_and_moves_back_in_one_undo(tmp_path):
    _project(tmp_path, "scene")
    scene = _doc(tmp_path, "scene")

    def start_of(folder, item, part, use, times, doc=None):     # the card starts at "drop" + x / 100
        doc = doc or Document.open(folder, item, toy.KIND)
        return times.get("drop", 0.0) + doc.item(part)["x"] / 100 if doc.has(part) else None
    links.register("toy", start_of)
    x0 = scene.item("card")["x"]
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "drop", "at": 2.0}},
                      {"op": "marker.add", "args": {"name": "Card · sound", "at": 0.0, "id": "mk_cue"}},
                      {"op": "marker.follow", "target": ["mk_cue"], "args": {"item": "scene", "part": "card"}}], SAM)
    assert M.at(tmp_path, "Card · sound") == pytest.approx(2.0 + x0 / 100)       # placed in the same step
    assert links.listing(tmp_path)[0]["from"] == "scene#card"

    M.edit(tmp_path, [{"op": "marker.move", "target": [M.find(M.listing(tmp_path), "drop")["id"]],
                       "args": {"at": 5.0}}], AGENT)                            # in Sound, the scene closed
    assert M.at(tmp_path, "Card · sound") == pytest.approx(5.0 + x0 / 100)

    desk.undo([M.open_to_change(tmp_path)], AGENT)              # the agent's "drop" move and the follow, as one
    assert (M.at(tmp_path, "drop"), M.at(tmp_path, "Card · sound")) == (2.0, pytest.approx(2.0 + x0 / 100))

    scene.apply([{"op": "layer.move", "target": ["card"], "args": {"x": 300}}], SAM)    # the app's own refresh
    assert links.refresh(tmp_path, SAM, docs={"scene": scene}) == ["Card · sound"]
    assert M.at(tmp_path, "Card · sound") == pytest.approx(5.0)
    with pytest.raises(RostrumError, match="moves with it"):
        M.edit(tmp_path, [{"op": "marker.move", "target": ["mk_cue"], "args": {"at": 1.0}}], SAM)

    scene.apply([{"op": "layer.remove", "target": ["card"]}], SAM)
    links.refresh(tmp_path, SAM, docs={"scene": scene})
    assert "is gone" in links.problems(tmp_path)[0]
