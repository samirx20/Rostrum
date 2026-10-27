"""The view menu's steps ("Fit · 53 %", ViewControls.qml) as Ctrl+K commands, from the one list the menu reads too
(`viewEntries`), so the command bar and the menu never differ: Fit the frame, Fit everything, Zoom 25 – 400 %, Zoom in,
Zoom out, Zoom to selection, Look through the frame, snapping. A command asks the menu to do its step (`viewRequested`:
the zoom lives on the canvas item, QML). A slot mix-in for Bridge2D."""
from __future__ import annotations

from PySide6.QtCore import Slot
from rostrum_gui.parts import SlotMixin

ZOOMS = (25, 50, 100, 200, 400)
# (value, label, keys, extra search words): the menu's first group; the commands add Zoom in / out and the switches.
STEPS = (("fit", "Fit the frame", "Ctrl 0", "view zoom fit frame"),
         ("everything", "Fit everything", "Shift 1", "view zoom fit all world"),
         *((str(p), f"{p} %", "Ctrl 1" if p == 100 else "", f"view zoom {p} percent") for p in ZOOMS),
         ("sel", "Zoom to selection", "F", "view fit selected layer"),
         ("look", "Look through the frame", "Shift C", "view camera preview"))
EXTRA = (("in", "Zoom in", "Ctrl =", "view bigger magnify"), ("out", "Zoom out", "Ctrl -", "view smaller"))


class ViewCommands(SlotMixin):
    @Slot(result="QVariantList")
    def viewEntries(self):
        """The view menu's zoom part, under one "Zoom" heading: Zoom in / out, then the steps that apply now (Zoom to
        selection needs a layer picked); Look through the frame on its own after them (the menu adds the switches)."""
        zoom = [{"value": v, "label": label, "keys": keys, "group": "a"} for v, label, keys, _ in (*EXTRA, *STEPS)
                if v != "look" and (v != "sel" or self.selected_layers())]
        zoom[0]["heading"] = "Zoom"
        return zoom + [{"value": v, "label": label, "keys": keys, "group": "l"} for v, label, keys, _ in STEPS if v == "look"]

    def _commands(self):
        have = {e["value"] for e in self.viewEntries()}
        mine = [(v, f"Zoom {label}" if v[0].isdigit() else label, keys, words) for v, label, keys, words in (*STEPS, *EXTRA)
                if v in have or v in ("in", "out")]
        mine.append(("snap", f"Turn snapping {'off' if self.snap.on else 'on'}", "", "view snap magnet"))
        return super()._commands() + [{"key": f"view:{v}", "label": label, "hint": "View", "keys": keys.replace(" ", "+"),
                                       "words": words, "weight": 1, "do": lambda v=v: self.viewRequested.emit(v)}
                                      for v, label, keys, words in mine]
