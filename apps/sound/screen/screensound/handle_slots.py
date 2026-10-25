"""Dragging an item's handles (a slot mix-in for SoundBridge; handles.py has the rules): what is under the pointer
(`handleAt` in the arrangement, `rollHandleAt` in the Editor: a note's right or left end), and the drag itself, one gesture
for every selected item of that kind (`beginHandle`, `handleTo`; `endDrag` names the step).
"""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.edits import Drag

from . import handles


class HandleSlots:
    @Slot(str, float, float, float, result="QVariantMap")
    def handleAt(self, track_id, t, y, tol):
        """{id, handle} of a clip handle under the pointer in a track's row (`y` 0..1 down the row); {} for none.
        Handles show on selected clips, so only those take them (a click elsewhere on a clip picks it)."""
        row = next((r for r in self._view["rows"] if r["id"] == track_id), None)
        for b in (row["blocks"] if row else []):
            if b["type"] == "clip" and b["id"] in self.selectedIds:
                rows, row = b.get("rows", 1), b.get("row", 0)
                if rows > 1 and not row <= y * rows < row + 1:
                    continue                                  # stacked: only its own row of the lane
                h = handles.at(b, t, y * rows - row, tol)
                if h:
                    return {"id": b["id"], "handle": h}
        return {}

    @Slot(float, float, float, result="QVariantMap")
    def rollHandleAt(self, t, row, tol):
        """{id, handle} when the pointer is on a note's end in the Editor (inside the note: handles.edge): "length" on
        its right end, "noteStart" on its left; {} otherwise."""
        for b in self._view["roll"].get("blocks", []):
            if b["type"] != "note" or int(round(row)) not in b["keys"]:
                continue
            near = handles.edge(b["dur"], tol)
            if 0 <= b["t"] + b["dur"] - t <= near:
                return {"id": b["id"], "handle": "length"}
            if 0 <= t - b["t"] <= near:
                return {"id": b["id"], "handle": "noteStart"}
        return {}

    @Slot(str, str, result=bool)
    def beginHandle(self, item_id, handle):
        """Press on a handle: a trim, fade, level, stretch or a note's length, for every selected item of that kind
        at once, one gesture."""
        drawn = self._drag is not None and bool((self._grab or {}).get("drawn"))   # a note just drawn: its length joins that step
        if not drawn:
            self.endDrag()
        if item_id not in self.selectedIds:
            self.select(item_id)

        def go():
            grabs = handles.grab(self.doc, self.selectedIds, handle)
            if drawn and "press" in self._grab:            # the new note's end follows the pointer from the press
                grabs = handles.drawn(grabs, self._grab["press"], self.doc.data, self._grid_now)
            self._grab = {"handle": handle, "grabs": grabs, "drawn": drawn}
            if not drawn:
                self._drag = Drag(self.doc, self.who, handles.NAMES[handle])
        return self._guard(go)

    def _draw_note(self, call, press):
        """The Draw tool's press on a key: the new note, selected, inside one open gesture "Draw note" that stays open
        until the release (`endDrag`), so dragging on to set its length is the same one undo step (`press`: the pointer's
        time, where that drag is measured from). Returns its id."""
        self.endDrag()
        before = {n["id"] for n in self.doc.item(self._track).get("notes", [])}

        def go():
            self._drag = Drag(self.doc, self.who, "Draw note")
            self._grab = {"drawn": True, "press": press}
            self._drag.preview(call if isinstance(call, list) else [call])     # (a chord: the note and its `note.chord`)
        if not self._guard(go):
            self.cancelDrag()
            return ""
        new = [n["id"] for n in self.doc.item(self._track)["notes"] if n["id"] not in before]
        if new:
            self._pick(new if len(new) > 1 else new[:1])      # a chord: all its notes, so the drag on sets them all
        root = call[0]["args"].get("id") if isinstance(call, list) else None      # the clicked note, not another tone
        return root if root in new else new[0] if new else ""

    @Slot(float, float, bool)
    def handleTo(self, dt, dy, free):
        """A handle's move from the press: dt seconds, dy row heights (the level line); snapped unless free."""
        g = self._grab
        if self._drag is not None and g and "handle" in g:
            self._guard(lambda: self._drag.preview(handles.calls(self.doc, g["grabs"], g["handle"], dt, dy, free, self._grid_now)))
