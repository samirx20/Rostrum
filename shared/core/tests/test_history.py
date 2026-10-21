"""Undo / redo per author, a drag is one step, loud all-or-nothing errors, save / load."""
import json

import pytest

from rostrum_core import Document, RostrumError, Who, codes, toy

SAM, AGENT = Who.person("sam"), Who.agent("claude-code")
CAM = {"op": "camera.set", "target": ["cam_1"], "args": {"dof": True}}


def x(doc):
    return doc.item("card")["x"]


def test_drag_is_one_step_and_undo_redo_are_per_author():
    doc = toy.sample()
    with doc.gesture("Move card", SAM) as g:
        for v in range(10, 110, 10):
            g.preview({"op": "layer.move", "target": ["card"], "args": {"x": v}})
    assert x(doc) == 100 and doc.seq == 1
    doc.apply(CAM, AGENT)
    doc.undo(SAM)                                    # the person's Ctrl+Z skips the agent's change
    assert x(doc) == 0 and doc.item("cam_1")["dof"] is True
    doc.redo(SAM)
    assert x(doc) == 100
    doc.undo(AGENT)
    assert doc.item("cam_1")["dof"] is False and x(doc) == 100
    assert len(doc.history.changes) == 5             # undo and redo are new steps; history only grows


def test_cancelled_or_failed_drag_records_nothing():
    doc = toy.sample()
    with doc.gesture("Move card", SAM) as g:
        g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 50}})
        g.cancel()
    with pytest.raises(RostrumError):
        with doc.gesture("Move card", SAM) as g:
            g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 50}})
            g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 99999}})
    assert x(doc) == 0 and doc.seq == 0


def test_undo_refuses_when_someone_changed_the_same_thing_later():
    doc = toy.sample()
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 5}}, SAM)
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 9}}, AGENT)
    with pytest.raises(RostrumError) as e:
        doc.undo(SAM)
    assert e.value.code == codes.CONFLICT and "agent:claude-code" in e.value.line() and x(doc) == 9


def test_failing_op_applies_nothing_and_names_the_op():
    doc = toy.sample()
    calls = [CAM, {"op": "layer.move", "target": ["crad"], "args": {"x": 1}}]
    with pytest.raises(RostrumError) as e:
        doc.apply(calls, AGENT)
    err = e.value.to_dict()
    assert err["code"] == codes.NOT_FOUND and err["where"] == "op 2 of 2 (layer.move)"
    assert err["hint"] == "Did you mean card?"
    assert doc.item("cam_1")["dof"] is False and doc.seq == 0
    for bad, code in [({"op": "layer.mvoe", "target": ["card"]}, codes.UNKNOWN_OPERATION),
                      ({"op": "layer.move", "target": ["card"], "args": {"x": 1e9}}, codes.BAD_ARGUMENT),
                      ({"op": "camera.set", "target": ["cam_1"], "args": {"aperture": 4}}, codes.BAD_ARGUMENT)]:
        with pytest.raises(RostrumError) as e:
            doc.apply(bad, AGENT)
        assert e.value.code == code
    assert doc.seq == 0


def test_save_open_round_trip_with_versions_and_outside_change(tmp_path):
    doc = toy.sample(tmp_path, "itm_card")
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 5}}, SAM)
    doc.mark_version("first")
    doc.apply(CAM, AGENT)
    doc.save()
    again = Document.open(tmp_path, "itm_card", toy.KIND)
    assert again.data == doc.data and again.seq == 2 and again.who_changed("cam_1", "dof").who == AGENT
    again.undo(SAM)                                  # undo state survives the round trip
    assert x(again) == 0
    again.restore_version("first", SAM)
    assert x(again) == 5 and again.item("cam_1")["dof"] is False
    # someone edits the file by hand: recorded as an outside change on open, never silently
    path = tmp_path / "docs" / "itm_card.toy"
    file = json.loads(path.read_text(encoding="utf-8"))
    file["doc"]["layers"][2]["x"] = 77
    path.write_text(json.dumps(file), encoding="utf-8")
    opened = Document.open(tmp_path, "itm_card", toy.KIND)
    assert x(opened) == 77 and opened.history.changes[-1].who.kind == "outside"
    hist = tmp_path / ".rostrum" / "itm_card.history.jsonl"
    hist.write_text(hist.read_text(encoding="utf-8") + "{broken\n", encoding="utf-8")
    with pytest.raises(RostrumError, match="line 5"):
        Document.open(tmp_path, "itm_card", toy.KIND)
