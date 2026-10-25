"""Ctrl+K lists a key-map job only while it can do something visible (the same "valid when" idea as an action's, for the
jobs the window or a route runs): Beat steps need a sound with a tempo, the drawing keys a drawing, A a layer picked,
the nudges a layer picked, and the Move tool is not offered while it is the tool. One table; `rows` drops the jobs that would do nothing now."""
from __future__ import annotations

from . import levels

WHEN = {
    "prev_beat": lambda b: b.soundtrack.hasBeats,
    "next_beat": lambda b: b.soundtrack.hasBeats,
    "new_drawing": lambda b: b.painter.drawing() is not None,
    "copy_drawing": lambda b: b.painter.drawing() is not None,
    "onion": lambda b: b.painter.drawingId != "",
    "hold_longer": lambda b: b.painter.drawingId != "",
    "hold_shorter": lambda b: b.painter.drawingId != "",
    "animated_rows": lambda b: any(i != "frame" for i in b.selected_layers()),     # the Frame has no animated rows
    "next_item": lambda b: bool(levels.siblings(b.doc, b.comp_id)),             # Tab walks the layers of this level
    "prev_item": lambda b: bool(levels.siblings(b.doc, b.comp_id)),
    "go_out": lambda b: bool(b.selected_layers()) and bool(levels.parent_group(b.doc, b.selected_layers()[-1])),
    "move_tool": lambda b: b.tool != "move",
    **{f"nudge_{d}{s}": (lambda b: bool(b.selected_layers()))          # the arrows move what is picked; nothing picked: no row
       for d in ("left", "right", "up", "down") for s in ("", "_big", "_fine")},
}


def rows(bridge, jobs: list[dict]) -> list[dict]:
    """`jobs`: job_rows.rows' list ("job:<name>" keys)."""
    return [r for r in jobs if not (r["key"].startswith("job:") and r["key"][4:] in WHEN and not WHEN[r["key"][4:]](bridge))]
