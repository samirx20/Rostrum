"""Drawing a note is one undo step ("Draw note"), however far the pointer drags on, and the new note is selected."""
from test_select import bridge, drag  # noqa: F401  (the fixture: a small song, the engine stood in for)


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



def test_the_screens_blocks_follow_every_edit(bridge):  # noqa: F811
    """What the screen shows for the lead row and the roll, kept as the QML does (whole lists, patches, resets,
    block_patch.py), always equals the song: a missed patch would be a note missing from the screen, or one that
    stays after its undo. The layouts (`tracks`, `roll`) say nothing for a note's edit (critic r4 M4)."""
    import json
    from screensound.block_patch import apply
    m, heard = bridge.trackRows, []
    row = next(i for i in range(m.rowCount()) if m.rows[i]["id"] == "lead")
    role = lambda: m.data(m.index(row), m._ids["blocks"])        # noqa: E731  the row model's "blocks" role
    screen = {"row": role(), "roll": bridge.rollBlocks}
    def patch(k, gone, put):
        screen[k] = apply(screen[k], gone, put)
    m.dataChanged.connect(lambda *_: screen.update(row=role()))
    bridge.blocksPatched.connect(lambda k, g, p: k == "lead" and patch("row", g, p))
    bridge.blocksReset.connect(lambda k: k == "lead" and screen.update(row=role()))
    bridge.rollPatched.connect(lambda g, p: patch("roll", g, p))
    bridge.rollBlocksChanged.connect(lambda: screen.update(roll=bridge.rollBlocks))
    for s in ("timelineChanged", "rollChanged"):
        getattr(bridge, s).connect(lambda s=s: heard.append(s))

    def same():
        key = lambda bl: sorted(json.dumps(b, sort_keys=True) for b in bl)       # noqa: E731
        truth = next(r for r in bridge.rows_now() if r["id"] == "lead")["blocks"]
        assert key(screen["row"]) == key(truth) and key(screen["roll"]) == key(bridge._view["roll"]["blocks"])
    nid = bridge.drawAt(1.0, 62)
    bridge.endDrag()
    same()
    assert heard == [] and all("blocks" not in r for r in bridge.tracks) and "blocks" not in bridge.roll
    drag(bridge, nid, 0.5, 2)
    same()
    bridge.undo()
    same()
    bridge.undo()
    same()
    assert nid not in {b["id"] for b in screen["roll"]}
    bridge.redo()
    same()
