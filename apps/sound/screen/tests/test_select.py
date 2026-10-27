"""Select first, then act: what would break silently. A drag of several items is one undo step; cut and paste are
one undo step each; Shift while dragging keeps the pitch (only in time) and Ctrl, not Shift, turns snapping off.
The engine is replaced by a stand-in (sound is checked by listening)."""
import sys
from pathlib import Path

import pytest
from PySide6.QtGui import QGuiApplication

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document  # noqa: E402
from rostrum_sound import KIND, run_source  # noqa: E402
from screensound import playback  # noqa: E402
from screensound.bridge import SoundBridge  # noqa: E402
from test_screen import FakeEngine  # noqa: E402

SRC = '''
tempo(120); beats_per_bar(4)
lead = track("lead", builtIn="feltPiano")
lead.note("C4", at=beat(4), dur=beats(1))
lead.note("E4", at=beat(6), dur=beats(1))
lead.note("G4", at=beat(8), dur=beats(1))
'''
A, B, C = "lead.n2000", "lead.n3000", "lead.n4000"


@pytest.fixture
def bridge(monkeypatch):
    QGuiApplication.instance() or QGuiApplication([])
    monkeypatch.setattr(playback, "open_engine", FakeEngine)
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SRC, "song.py"))
    b = SoundBridge(doc)
    yield b
    b.close()
    import shiboken6
    shiboken6.delete(b)        # freed, as a closed song is: its jobs waiting for a frame never run ahead of the next test's


def drag(b, item, dt, dsemi, free=False, only_time=False):
    assert b.beginDrag(item)
    for f in (0.3, 0.6, 1.0):
        b.dragTo(dt * f, round(dsemi * f), free, only_time, False, 0.0)
    b.endDrag()


def test_drag_of_many_is_one_undo_step(bridge):
    doc, before = bridge.doc, len(bridge.doc.history.changes)
    bridge.selectMany([A, B, C])
    drag(bridge, B, 0.5, 2)                              # +1 beat, +2 semitones, all three
    assert [doc.item(i)["at"] for i in (A, B, C)] == [{"beat": 5.0}, {"beat": 7.0}, {"beat": 9.0}]
    assert [doc.item(i)["pitch"] for i in (A, B, C)] == ["D4", "F#4", "A4"]
    assert len(doc.history.changes) == before + 1
    bridge.undo()
    assert [doc.item(i)["at"] for i in (A, B, C)] == [{"beat": 4}, {"beat": 6}, {"beat": 8}]


def test_shift_is_only_in_time_and_ctrl_is_free(bridge):
    doc = bridge.doc
    bridge.select(A)
    drag(bridge, A, 0.5, 3, only_time=True)              # Shift: the pitch stays
    assert doc.item(A)["pitch"] == "C4"
    drag(bridge, A, 0.1, 0, free=True)                   # Ctrl: off the quarter-beat grid
    assert doc.item(A)["at"] == {"beat": 5.2}


def test_cut_and_paste_are_one_undo_step_each(bridge):
    doc, n = bridge.doc, len(bridge.doc.history.changes)
    bridge.selectMany([A, B])
    assert bridge.run("cut")
    assert not doc.has(A) and not doc.has(B) and len(doc.history.changes) == n + 1
    bridge.setTime(6.0)
    bridge.select("lead")
    assert bridge.run("paste")
    assert len(doc.history.changes) == n + 2
    new = bridge.selectedIds                             # what the paste made is selected
    assert [doc.item(i)["at"] for i in new] == [{"beat": 12.0}, {"beat": 14.0}]
    bridge.undo()
    assert not any(doc.has(i) for i in new)


def test_a_locked_tracks_note_refuses_an_edit_loudly(bridge):
    doc = bridge.doc
    bridge.select("lead")
    assert bridge.run("lock")
    bridge.select(A)
    assert not bridge.nudge("grid", 1)                   # refused, said, nothing moved
    assert "locked" in bridge.status and doc.item(A)["at"] == {"beat": 4}
    from rostrum_core import RostrumError, Who
    with pytest.raises(RostrumError):                    # an agent too
        doc.apply([{"op": "note.set", "target": [A], "args": {"vel": 0.1}}], Who.agent("claude"))


def test_trim_by_handle_and_note_length_are_one_undo_step_each(bridge):
    doc, n = bridge.doc, len(bridge.doc.history.changes)
    bridge.selectMany([A, B])
    assert bridge.beginHandle(A, "length")
    for f in (0.3, 1.0):
        bridge.handleTo(0.25 * f, 0, False)
    bridge.endDrag()
    assert [doc.item(i)["dur"] for i in (A, B)] == [{"beats": 1.5}, {"beats": 1.5}]
    assert len(doc.history.changes) == n + 1
    bridge.undo()
    assert doc.item(A)["dur"] == {"beats": 1} and set(bridge.selectedIds) == {A, B}      # undo selects them again


def test_landing_a_bar_on_a_marker_is_one_undo_step(bridge):
    from rostrum_sound.doc import tempo
    doc, n = bridge.doc, len(bridge.doc.history.changes)
    bridge.setTime(9.0)
    bridge.markerAt(9.0)
    bridge.finishRename(bridge.renaming, "logo")         # M, then the name, Enter
    assert bridge.actions.ask("fit_bar")                 # Start a bar here…: its popover's session, bar 5, kept
    bridge.actions.amounts.setValue("bar", 5)
    bridge.actions.amounts.keep()
    assert abs(tempo.seconds_at(doc.data, 16) - 9.0) < 1e-6   # bar 5 starts on the marker; beats follow
    assert len(doc.history.changes) == n + 3             # add, rename, land: one step each
    bridge.undo()
    assert doc.data["tempo"] == 120


def test_loop_with_no_range_makes_one_and_clearing_it_ends_the_loop(bridge):
    bridge.setTime(0.0)
    bridge.toggleLoop()
    assert bridge.looping and len(bridge.timeRange) == 2 and bridge.timeRange[1] > bridge.timeRange[0]
    assert bridge.transport.loop == tuple(bridge.timeRange)
    bridge.clearRange()
    assert not bridge.looping and bridge.transport.loop is None
    bridge.toggleLoop()
    bridge.toggleLoop()
    assert not bridge.looping and bridge.timeRange        # off, the range stays


def test_loop_button_range_does_not_put_range_actions_before_the_selected_track(bridge):
    bridge.select("lead")
    bridge.toggleLoop()
    assert bridge.looping and bridge.timeRange
    assert not bridge._facts().on_range                   # the loop's own range: the track's actions stay first
    bridge.setRange(1.0, 3.0, True)
    assert bridge._facts().on_range                       # a range a person drew after: it is what they mean


def test_split_here_from_the_clip_menu_is_one_undo_step(bridge):
    doc = bridge.doc
    doc.run_script("song2.py", run_source(SRC + 'lead.clip("a.wav", at=10, length=4)\n', "song2.py"))
    clip = next(c["id"] for t in doc.data["tracks"] for c in t.get("clips", []))
    rows = bridge.blockMenu(clip, 12.0)
    assert any(r["label"] == "Split here" for r in rows) and any(r["label"] == "Duplicate" for r in rows)
    before = len(doc.history.changes)
    assert bridge.runAt(next(r["value"] for r in rows if r["label"] == "Split here"))
    assert len(doc.history.changes) == before + 1
    assert len([c for t in doc.data["tracks"] for c in t.get("clips", [])]) == 2
    bridge.undo()
    assert len([c for t in doc.data["tracks"] for c in t.get("clips", [])]) == 1


def test_select_inside_a_range_works_with_a_track_picked(bridge):
    """A new track is picked, so a range drawn then must still select what is inside it (critic r4 M2: KeyError)."""
    bridge.select("lead")
    bridge.setRange(0.0, 3.0, True)
    bridge.actions.run("inside")
    picked = bridge.selectedIds
    assert picked and "lead" not in picked and all(bridge.doc.item(i)["type"] != "track" for i in picked)



def test_many_notes_fold_to_exactly_the_merge_of_each_notes_rows(bridge):
    """Many notes picked: the panel evaluates each alike group once and reads the rest's values (many_rows.py). It
    must show exactly what merging every note's own rows shows: notes on a struck guitar beside a piano's (other
    rows apply), values that differ, values alike, a field set on some only, a length read across a tempo change,
    hits and a track with them (mixed kinds)."""
    from rostrum_core import Who
    from rostrum_gui import many
    from screensound import inspect, many_rows, output_pick

    def op(name, target, **args):
        return {"op": name, "target": target, "args": args}
    d = bridge.doc
    calls = [op("track.add", [], id="gtr", instrument="model", model="guitar"), op("tempo.add", [], at={"beat": 12}, bpm=90)]
    calls += [op("note.add", ["lead"], id=f"lead.x{i}", pitch=["C4", "D4", "E4"][i % 3], at={"beat": 10 + i},
                 dur={"beats": 2 if i == 6 else 1}, **({"vel": 0.5} if i % 2 else {}), **({"pan": 0.25} if i == 5 else {}))
              for i in range(8)]
    calls += [op("note.add", ["gtr"], id=f"gtr.x{i}", pitch="G3", at={"beat": 2 * i}, dur={"beats": 1}, vel=0.5) for i in range(9)]
    calls += [op("track.add", [], id="kit", instrument="kit", kit="classic")]
    calls += [op("hit.add", ["kit"], id=f"kit.x{i}", drum="kick" if i % 2 else "snare", at={"beat": i}, vel=0.5) for i in range(4)]
    d.apply(calls, Who.person())
    made = [c["args"]["id"] for c in calls if c["op"] == "note.add"]
    guitar = [i for i in made if i.startswith("gtr.")]
    hits = [c["args"]["id"] for c in calls if c["op"] == "hit.add"]
    for picked in ([A, B, C, *made], made[3:], guitar, guitar[:4] + made[:5], hits + made, ["lead", *made, *hits]):
        bridge.selectMany(picked)
        items = [d.item(i) for i in bridge._kit.selection]
        each = [inspect.musical_rows(it, bridge._item_rows(it), d.data) for it in items]
        folded = many_rows.merged(bridge, items, d.data)
        assert folded is not None and folded == many.merge(each)
        assert bridge._rows() == output_pick.without_none(many.merge(each))
        rows = {r["id"]: r for r in folded if r["row"] == "param"}
        if picked[0] in hits or picked[0] == "lead":                                    # mixed kinds: what they share
            assert "dur" not in rows and (picked[0] == "lead" or rows["at"]["mixed"] and rows["vel"]["mixed"])
            continue
        assert rows["at"]["mixed"] and rows["dur"]["mixed"] == ("lead.x6" in picked)   # (2 beats; the rest 1)
        assert rows["position"]["valid"] == (picked == guitar)                          # only while every note is struck
    # each merge keeps the keys and the "differs" proofs of the one before (a note changed only in a plain value keeps
    # its group; the item that differed is asked first): after a move, its undo and redo, values made alike again and
    # a time written in another form, still exactly the merge of every note's own rows
    lead = [i for i in made if i.startswith("lead.")]
    steps = (lambda: d.apply([op("note.move", lead[:4], by={"beats": 1})], Who.person()), bridge.undo, bridge.redo,
             lambda: d.apply([op("note.set", lead, vel=0.5)], Who.person()),
             lambda: d.apply([op("note.set", lead[1:2], at=7.5)], Who.person()), bridge.undo)
    for step in steps:
        step()
        bridge.selectMany(lead + hits)
        items = [d.item(i) for i in bridge._kit.selection]
        each = [inspect.musical_rows(it, bridge._item_rows(it), d.data) for it in items]
        assert many_rows.merged(bridge, items, d.data) == many.merge(each)


def test_esc_during_a_box_gives_back_the_selection_from_before_it(bridge):
    bridge.pickMany([C, A])                              # anchor A (Shift's run starts there)
    bridge.boxSelect(["lead"], 0.0, 60.0, False)         # a box over the whole track: it takes what it touches
    assert bridge.selectedIds != [C, A]
    bridge.boxSelect(["lead"], 0.0, 0.1, False)          # the box shrinks to nothing
    bridge.cancelBox()                                   # Esc
    assert bridge.selectedIds == [C, A] and bridge._picks.anchor == A
    bridge.boxSelect(["lead"], 0.0, 60.0, True)          # the next box starts from that selection (Ctrl adds)
    bridge.endBox()
    bridge.cancelBox()                                   # an Esc after the box ended changes nothing
    assert set(bridge.selectedIds) >= {A, C} and len(bridge.selectedIds) > 2
