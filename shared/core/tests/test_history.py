"""Undo / redo per author, a drag is one step, loud all-or-nothing errors, save / load."""
import json

import pytest

from rostrum_core import Document, RostrumError, Who, codes, live, toy

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


def test_undo_while_a_drag_or_popover_is_open_is_refused_and_changes_nothing():
    doc = toy.sample()
    doc.apply(CAM, SAM)
    with doc.gesture("Strum", SAM) as g:                 # a live amounts popover is a gesture too
        g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 40}})
        with pytest.raises(RostrumError, match="Strum"):
            doc.undo(SAM)                                # stepping the history under the preview would mix both
    assert x(doc) == 40 and doc.item("cam_1")["dof"] is True and doc.seq == 2


def test_an_open_box_that_says_how_it_ends_makes_way_for_another_edit():
    """Critic r10: an open Stagger box made Ctrl+G say "being dragged by a person" and Esc then lost the stagger.
    A box with `interrupt` (keep, as Enter does) ends first: the other edit runs on top, and Ctrl+Z takes back
    the box's own change first; a drag a person holds (no `interrupt`) refuses in plain words."""
    doc = toy.sample()
    g = doc.gesture("Stagger 2 layers", SAM).__enter__()
    g.interrupt = lambda: g.__exit__(None, None, None)
    g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 40}})
    doc.apply(CAM, SAM)
    assert doc.history.changes[0].label == "Stagger 2 layers" and len(doc.history.changes) == 2
    assert x(doc) == 40 and doc.item("cam_1")["dof"] is True
    g = doc.gesture("Stagger 2 layers", SAM).__enter__()
    g.interrupt = lambda: g.__exit__(None, None, None)
    g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 70}})
    doc.undo(SAM)                                        # kept, then taken back: the card is where it was
    assert x(doc) == 40 and doc.history.changes[-1].label == "Undid: Stagger 2 layers"
    with doc.gesture("Move card", SAM) as g:
        g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 90}})
        with pytest.raises(RostrumError, match="is still open") as e:
            doc.apply(CAM, SAM)
        assert "dragged by a person" not in e.value.person()


def test_a_drag_back_to_the_start_takes_its_steps_back_and_a_click_sends_nothing():
    doc, heard = toy.sample(), []
    doc.subscribe(lambda ev: heard.append(ev.kind))
    with doc.gesture("Move card", SAM) as g:
        g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 50}})
        g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 0}})
    assert heard == ["preview", "preview", "reset"] and doc.seq == 0     # listeners saw x 50: they are told it is back
    heard.clear()
    with doc.gesture("Move card", SAM):                                   # a press and a release, no step (a click)
        pass
    assert heard == [] and doc.seq == 0 and x(doc) == 0


def test_a_drag_taken_back_says_what_it_undid():
    doc, heard = toy.sample(), []
    doc.subscribe(heard.append)
    with doc.gesture("Move card", SAM) as g:
        g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 50}})
        g.cancel()
    back = heard[-1]
    assert back.kind == "reset" and [(e.id, e.path, e.value) for e in back.edits] == [("card", ["x"], 0)]


def test_undo_refuses_when_someone_changed_the_same_thing_later():
    doc = toy.sample()
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 5}}, SAM)
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 9}}, AGENT)
    with pytest.raises(RostrumError) as e:
        doc.undo(SAM)
    assert e.value.code == codes.CONFLICT and "Claude changed" in e.value.line() and x(doc) == 9


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
    with pytest.raises(RostrumError, match="line 7"):
        Document.open(tmp_path, "itm_card", toy.KIND)


def test_a_bad_value_is_refused_by_the_document_check_and_on_open(tmp_path):
    """RELEASE line 13: every field of every kind is checked against its own data (a frame rate of 0 crashed 2D's
    drawing); a call that would store one fails, and a file holding one is refused in words, never half-opened."""
    doc = toy.sample(tmp_path, "itm_card")
    doc.save()
    assert json.loads((tmp_path / "docs" / "itm_card.toy").read_text(encoding="utf-8"))["saved_by"]   # line 14
    with pytest.raises(RostrumError, match="out of range"):
        doc.run_script("bad.py", {**doc.data, "layers": [{**doc.data["layers"][0], "focal": 0}]})
    path = tmp_path / "docs" / "itm_card.toy"
    file = json.loads(path.read_text(encoding="utf-8"))
    file["doc"]["layers"][0]["focal"] = 0
    path.write_text(json.dumps(file), encoding="utf-8")
    with pytest.raises(RostrumError, match=r"damaged.*focal=0 is out of range") as e:
        Document.open(tmp_path, "itm_card", toy.KIND)
    assert e.value.code == codes.CHECK_FAILED and json.loads(path.read_text(encoding="utf-8")) == file   # untouched
    (tmp_path / ".rostrum" / "itm_card.history.jsonl").unlink()      # a file with no history is checked the same
    with pytest.raises(RostrumError, match="focal=0 is out of range"):
        Document.open(tmp_path, "itm_card", toy.KIND)


def test_a_drag_that_writes_0_as_0_0_still_opens(tmp_path):
    """H31 F7 walk: a drag that also tied the layer rewrote its start 0 as 0.0; Python calls them equal, so no change was recorded,
    but the file held 0.0 and its history no longer added up ("doesn't add up to its own last step" on open)."""
    doc = toy.sample(tmp_path, "itm_card")
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 5}}, SAM)
    with doc.gesture("Move card", SAM) as g:
        g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 40}})
        g.preview([{"op": "layer.move", "target": ["card"], "args": {"x": 5.0}}, CAM])     # x unchanged, written 5.0
    doc.save()
    again = Document.open(tmp_path, "itm_card", toy.KIND)
    assert again.data == doc.data


def test_a_step_cut_off_by_a_crash_is_left_out_loudly_and_the_rest_opens(tmp_path):
    """S39: the history file is appended to; a crash mid-append cuts only its last line."""
    doc = toy.sample(tmp_path, "itm_card")
    doc.save()
    live.keep(doc)
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 5}}, SAM)
    doc.apply(CAM, AGENT)
    hist = tmp_path / ".rostrum" / "itm_card.history.jsonl"
    text = hist.read_text(encoding="utf-8")
    hist.write_text(text[:text.rstrip("\n").rfind("\n") + 30], encoding="utf-8")   # the agent's step half-written
    opened = Document.open(tmp_path, "itm_card", toy.KIND)
    assert opened.seq == 1 and x(opened) == 5 and "cut off" in opened.notes[0]
    opened.undo(SAM)
    opened.save()                                    # the cut-off line goes before the next whole one
    again = Document.open(tmp_path, "itm_card", toy.KIND)
    assert again.seq == 2 and x(again) == 0 and not again.notes


def test_an_old_layout_file_opens_unchanged_and_is_saved_in_the_new_one(tmp_path):
    """Files saved before S39: history rewritten whole with the starting document on line 1, an indented document."""
    doc = toy.sample(tmp_path, "itm_card")
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 5}}, SAM)
    doc.mark_version("first")
    doc.apply(CAM, AGENT)
    kind = toy.KIND
    lines = [json.dumps({"format": kind.format, "version": kind.version, "base": doc.base})]
    lines += [json.dumps(c.to_dict()) for c in doc.history.changes] + [json.dumps({"version": "first", "at": 1})]
    (tmp_path / ".rostrum").mkdir()
    (tmp_path / ".rostrum" / "itm_card.history.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / f"itm_card{kind.ext}").write_text(json.dumps(
        {"format": kind.format, "version": kind.version, "saved_by": "0.1.2", "doc": doc.data}, indent=1), encoding="utf-8")
    old = Document.open(tmp_path, "itm_card", kind)
    assert old.data == doc.data and old.seq == 2 and old.versions() == {"first": 1}
    old.undo(SAM)
    old.save()
    assert '"layout":2' in (tmp_path / ".rostrum" / "itm_card.history.jsonl").read_text(encoding="utf-8").split("\n")[0]
    new = Document.open(tmp_path, "itm_card", kind)
    assert new.data == old.data and new.seq == 3 and x(new) == 0 and new.item("cam_1")["dof"] is True
    new.restore_version("first", SAM)
    assert x(new) == 5 and new.item("cam_1")["dof"] is False


def test_setting_a_value_to_what_it_is_records_nothing():
    doc = toy.sample()
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 40}}, SAM)
    before = doc.seq
    assert doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 40}}, SAM) is None
    assert doc.seq == before and x(doc) == 40


def test_quick_repeats_merge_but_a_change_back_is_its_own_step():
    """A person's quick nudges of one field are one undo step; a switch turned on and off again (motion blur added then
    taken away) is two, so Ctrl+Z brings the first back."""
    doc = toy.sample()
    for v in (10, 20, 30):                                          # three quick nudges: one step
        doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": v}}, SAM)
    assert len(doc.history.changes) == 1
    doc.apply(CAM, SAM)
    doc.apply({"op": "camera.set", "target": ["cam_1"], "args": {"dof": False}}, SAM)   # back off at once: a step of its own
    assert len(doc.history.changes) == 3
    doc.undo(SAM)
    assert doc.item("cam_1")["dof"] is True


def test_undo_n_then_redo_n_in_order_is_never_refused_and_comes_back_exact():
    """Redo stopped after one step: the first redo counted as "a later change" that blocked the next (critic r8)."""
    doc = toy.sample()
    states = [doc.data]
    for v in (5, 9, 14):
        doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": v}}, SAM, join=False)
        states.append(doc.data)
    for n in range(3):
        doc.undo(SAM)
        assert doc.data == states[-2 - n]
    for n in range(3):
        doc.redo(SAM)
        assert doc.data == states[1 + n]
    assert doc.history.stuck() == {1, 2} and doc.data == doc.at_step(doc.seq)    # only the newest can be undone


def test_a_refused_redo_says_in_words_what_blocks_it():
    doc = toy.sample()
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 5}}, SAM)
    doc.undo(SAM)
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 9}}, AGENT)
    c = doc.history.last_redoable(SAM)
    with pytest.raises(RostrumError) as e:
        doc.redo_changes([c], SAM)
    line = e.value.line()
    assert "brought back" in line and "Claude changed some of the same things" in line and "card." not in line


def test_a_save_while_a_preview_is_open_writes_the_kept_song_not_the_preview(tmp_path):
    """Closing the window with a Repeat box open saved its preview with no history step (critic r8: 448 notes became
    2,240). Every save writes what the history leaves, live or not."""
    doc = toy.sample(tmp_path, "itm")
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 5}}, SAM)
    doc.save()
    live.keep(doc)
    with doc.gesture("Repeat", SAM) as g:
        g.preview({"op": "layer.move", "target": ["card"], "args": {"x": 400}})
        doc.save()                                   # Save, close or a timer while the box is open
        g.cancel()
    on_disk = json.loads((tmp_path / "docs" / f"itm{toy.KIND.ext}").read_text(encoding="utf-8"))
    assert on_disk["doc"] == doc.data and not doc.live.behind()
    again = Document.open(tmp_path, "itm", toy.KIND)
    assert x(again) == 5 and again.seq == 1 and again.data == again.at_step(again.seq)
