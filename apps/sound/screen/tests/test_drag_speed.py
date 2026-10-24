"""A drag re-makes only what it moves, and the sound waits for its release: what would break silently. A step that
re-makes only the changed tracks' rows must show exactly what a full rebuild shows; no render starts while a drag
is open, and its release renders once."""
from test_select import A, bridge  # noqa: F401  (the fixture: a small song, the engine stood in for)

from screensound import timeline


def full(b):
    root = b.doc.data
    return timeline.rows(root, b._open, b._folded), timeline.song(root)


def test_a_drag_step_shows_what_a_full_rebuild_shows(bridge):  # noqa: F811
    assert bridge.beginDrag(A)
    for dt in (0.4, 1.1, 2.3):
        bridge.dragTo(dt, 2, True, False, False, 0.0)
        assert (bridge._view["rows"], bridge._view["song"]) == full(bridge)
    bridge.endDrag()
    assert (bridge._view["rows"], bridge._view["song"]) == full(bridge)


def test_no_render_while_dragging_and_one_on_release(bridge):  # noqa: F811
    t, asked = bridge.transport, []
    t.renderer.request = asked.append
    assert bridge.beginDrag(A)
    bridge.dragTo(0.5, 0, True, False, False, 0.0)
    t.render()                                       # the debounce of an earlier edit fires mid-drag: it waits
    assert asked == [] and t.busy()
    bridge.endDrag()
    t.render()                                       # the release's change: one render
    assert len(asked) == 1
