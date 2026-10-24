"""Drawing a note is one undo step ("Draw note"), however far the pointer drags on, and the new note is selected."""
from test_select import bridge  # noqa: F401  (the fixture: a small song, the engine stood in for)


def test_draw_then_drag_longer_is_one_step_and_selected(bridge):  # noqa: F811
    doc, before = bridge.doc, len(bridge.doc.history.changes)
    nid = bridge.drawAt(1.0, 62)
    assert nid and bridge.selectedIds == [nid]
    d0 = doc.item(nid)["dur"]
    assert bridge.beginHandle(nid, "length")
    bridge.handleTo(1.5, 0, True)
    bridge.endDrag()
    assert len(doc.history.changes) == before + 1
    assert doc.history.changes[-1].label == "Draw note"
    assert doc.item(nid)["dur"] != d0                 # the drag lengthened it, inside that one step
    bridge.undo()
    assert not doc.has(nid)                           # one undo takes the whole note away


def test_plain_click_draw_is_one_step_after_release(bridge):  # noqa: F811
    doc, before = bridge.doc, len(bridge.doc.history.changes)
    nid = bridge.drawAt(1.0, 62)
    bridge.endDrag()
    assert len(doc.history.changes) == before + 1 and bridge.selectedIds == [nid]


def test_a_note_drawn_where_the_last_one_ends_is_kept(bridge):  # noqa: F811
    """A note's end handle sits inside it: a click just past its end is empty space, so Draw adds there (critic r4 M1)."""
    first = bridge.drawAt(1.0, 62)
    bridge.endDrag()
    b = next(x for x in bridge._view["roll"]["blocks"] if x["id"] == first)
    end, tol = b["t"] + b["dur"], 0.05                # tol: the roll's 6 px, in seconds
    assert bridge.rollHandleAt(end - 0.01, 62, tol).get("id") == first
    assert bridge.rollHandleAt(end + 0.01, 62, tol) == {} and bridge.rollAt(end + 0.01, 62, tol) == ""
    second = bridge.drawAt(end + 0.01, 62)
    bridge.endDrag()
    assert second and second != first and bridge.doc.has(first) and bridge.doc.has(second)
