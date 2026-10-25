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


def test_a_drawn_note_dragged_two_beats_is_two_beats_long(bridge):  # noqa: F811
    """The drag sets the end from where the press was, not from the Note ▾ length on top (critic r6 M2: 2 beats → 3)."""
    from screensound import timing
    root = bridge.doc.data
    t0 = timing.snap(4.0, root, False, None)            # a line (120 bpm: 0.5 s a beat)
    nid = bridge.drawAt(t0 + 0.01, 62)                    # pressed a pixel or so past the line
    assert bridge.beginHandle(nid, "length")
    bridge.handleTo(1.0 + 0.02, 0, False)                # two beats on, released just past the line
    bridge.endDrag()
    b = next(x for x in bridge._view["roll"]["blocks"] if x["id"] == nid)
    assert abs(b["t"] - t0) < 1e-6 and abs(b["dur"] - 1.0) < 1e-3


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
    from screensound.block_patch import apply, seen
    m, heard = bridge.trackRows, []
    row = next(i for i in range(m.rowCount()) if m.rows[i]["id"] == "lead")
    role = lambda: json.loads(m.data(m.index(row), m._ids["blocks"]))   # noqa: E731  the row model's "blocks" role (JSON text)
    roll = lambda: json.loads(bridge.rollBlocks)                         # noqa: E731
    screen = {"row": role(), "roll": roll()}
    def patch(k, text):
        screen[k] = apply(screen[k], json.loads(text))
    m.dataChanged.connect(lambda *_: screen.update(row=role()))
    bridge.blocksPatched.connect(lambda k, p: k == "lead" and patch("row", p))
    bridge.blocksReset.connect(lambda k: k == "lead" and screen.update(row=role()))
    bridge.rollPatched.connect(lambda p: patch("roll", p))
    bridge.rollBlocksChanged.connect(lambda: screen.update(roll=roll()))
    for s in ("timelineChanged", "rollChanged"):
        getattr(bridge, s).connect(lambda s=s: heard.append(s))

    def same():
        key = lambda bl: sorted(json.dumps(seen(b), sort_keys=True) for b in bl)   # noqa: E731  (as sent: in beats)
        truth = next(r for r in bridge.rows_now() if r["id"] == "lead")["blocks"]
        assert key(screen["row"]) == key(truth) and key(screen["roll"]) == key(bridge._view["roll"]["blocks"])
        by = {b["id"]: b for b in screen["roll"]}          # the velocity readout's blocks: the selected ones, as shown
        from screensound import velocity           # the velocity readout: the selected ones, as shown
        want = velocity.readout([{**by[i], "t": bridge._roll_by[i]["t"]} for i in bridge.selectedIds if i in by])
        assert bridge.rollPicked == want
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
    many = [i["id"] for i in bridge.doc.item("lead")["notes"]]     # every note of the row: one group "moved by"
    bridge.selectMany(many)
    assert bridge.nudge("grid", 1)
    same()
    bridge.undo()
    same()
    with bridge.doc.gesture("Repeat", bridge.who) as g:            # a preview taken back (Esc): its exact inverse
        g.preview([{"op": "note.duplicate", "target": many, "args": {"times": 3}}])
        same()
        g.cancel()
    same()
