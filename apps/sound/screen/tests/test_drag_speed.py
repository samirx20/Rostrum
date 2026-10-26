"""A drag re-makes only what it moves, and the sound waits for its release: what would break silently. A step that
re-makes only the changed tracks' rows must show exactly what a full rebuild shows; no render starts while a drag
is open, and its release renders once."""
from test_select import A, bridge  # noqa: F401  (the fixture: a small song, the engine stood in for)

from PySide6.QtCore import QCoreApplication
from rostrum_gui import after_frame
from rostrum_gui.pointer import wait_until
from screensound import timeline


def full(b):
    root = b.doc.data
    return timeline.rows(root, b._open, b._folded), timeline.song(root)


def shown(b):
    """What the screen holds against a fresh build: the rows, the song, and the roll's blocks (the blocks a step
    reuses are each note's own, block_memo.py: one left stale would show a note where it no longer is)."""
    track = b.doc.item(b._track)
    return ((b._view["rows"], b._view["song"], b._view["roll"]["blocks"])
            == (*full(b), timeline.blocks(track, b.doc.data)))


def test_a_drag_step_shows_what_a_full_rebuild_shows(bridge):  # noqa: F811
    assert bridge.beginDrag(A)
    for dt in (0.4, 1.1, 2.3):
        bridge.dragTo(dt, 2, True, False, False, 0.0)
        assert shown(bridge)
    bridge.endDrag()
    assert shown(bridge)
    bridge.undo()                                    # the note comes back where it was: so does its block
    assert shown(bridge)


def test_no_render_while_dragging_and_one_on_release(bridge):  # noqa: F811
    t, asked = bridge.transport, []
    t.renderer.request = asked.append
    assert bridge.beginDrag(A)
    bridge.dragTo(0.5, 0, True, False, False, 0.0)
    t.render()                                       # the debounce of an earlier edit fires mid-drag: it waits
    QCoreApplication.processEvents()
    assert asked == [] and t.busy()
    bridge.endDrag()
    t.render()                                       # the release's change: one render, after the frame (never dropped)
    assert asked == [] and t.busy()                  # (the compile waits for the next turn of the loop: play waits too)
    t.render()                                       # asked again before it ran: still that one render
    wait_until(lambda: asked, "the release's one render to be asked")      # (when the loop turns: a frame, or its timer)
    wait_until(lambda: not after_frame.pending(), "the render's turn to finish")
    assert len(asked) == 1, f"expected exactly one render after the release, got {len(asked)}"


def test_a_track_added_keeps_the_others_blocks_and_a_tempo_change_remakes_them(bridge):  # noqa: F811
    """Adding a track reuses every other track's row and blocks (block_memo.follow); a tempo change moves every block
    and must not show the old ones."""
    before = dict(bridge._made)
    bridge._apply([{"op": "track.add", "args": {"name": "Pad", "instrument": "synth"}}], "Add track")
    assert shown(bridge) and all(bridge._made[k] is r for k, r in before.items())
    bridge._apply([{"op": "doc.set", "target": ["root"], "args": {"tempo": 90}}], "Edit song")
    assert shown(bridge)
    bridge.undo()
    bridge.undo()
    assert shown(bridge)


def test_a_tempo_drag_shows_the_song_retimed_at_rest_at_the_drop_and_after_undo(bridge):  # noqa: F811
    """A tempo drag re-times every block: its steps draw the rows only when the pointer rests (rows_view REST_MS) and
    at the drop. The rows must never stay on an old tempo after either, nor after undo and redo."""
    from screensound.song_panel import SongPanel
    panel = SongPanel(bridge)
    panel.beginTempo()
    for bpm in (126, 133, 140):
        panel.scrubTempo(bpm)
    assert bridge._view["song"]["tempo"] == 140                       # the ruler follows each step
    bridge._rest.timeout.emit()                                       # the pointer rests
    assert shown(bridge)
    panel.scrubTempo(150)                                             # moved again, let go before resting
    panel.endScrub()
    assert bridge.doc.data["tempo"] == 150 and shown(bridge)
    bridge.undo()
    assert bridge.doc.data["tempo"] == 120 and shown(bridge)
    bridge.redo()
    assert shown(bridge)
