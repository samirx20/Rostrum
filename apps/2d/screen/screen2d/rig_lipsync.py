"""Lip sync… (UX_SPEC 3.23; `backend.lipsync`, qml/LipSyncSheet.qml): select a mouth swap set → the context bar's
Lip sync… opens a small sheet: the project's voice lines (rig_voice.py: Sound's own), a row per mouth shape with the
drawing guessed from its name (rig_mouths.py; pick another to fix a wrong guess), Apply = one `lipsync.apply` change
(keys on the set's Shows, held per sound). A line not heard before is listened to first, off the screen's thread (the
phone model: a few seconds to a minute); the sheet says so and Apply waits for it, then makes the one change.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d.names import display_name

from . import rig_mouths, rig_voice


class LipSyncSheet(QObject):
    changed = Signal()
    opened = Signal()
    _heard = Signal(object)             # an error, or None when the line's phones are in the cache

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._set, self._lines, self._line, self._shapes, self._busy = bridge, "", [], "", {}, False
        self._heard.connect(self._after)

    @Property(bool, notify=changed)
    def open(self):
        return bool(self._set)

    @Property(str, notify=changed)
    def what(self):
        return display_name(self.b.doc.item(self._set)) if self._set and self.b.doc.has(self._set) else ""

    @Property("QVariantList", notify=changed)
    def lines(self):
        """The made lines: {id, label, picked}."""
        return [{"id": ln["id"], "label": f'"{ln["text"]}" · {ln["song"]} · {ln["at"]:g} s', "picked": ln["id"] == self._line}
                for ln in self._lines if ln["file"]]

    @Property(str, notify=changed)
    def note(self):
        """What the person should know: lines without a voice yet, or that Apply listens first."""
        missing = sum(1 for ln in self._lines if not ln["file"])
        if self._busy:
            return "Listening to the line… (a few seconds to a minute)"
        if not self._lines:
            return "This project has no voice lines yet. Write one in RostrumSound."
        out = f"{missing} line{'s' if missing > 1 else ''} without a voice yet: Make voice in RostrumSound. " if missing else ""
        line = self._picked()
        if line and not rig_voice.heard(line):
            out += "Apply listens to this line first (a few seconds to a minute)."
        return out.strip()

    @Property("QVariantList", notify=changed)
    def rows(self):
        kids = self.b.doc.item(self._set).get("layers", []) if self._set else []
        return rig_mouths.rows(kids, self._shapes)

    @Property(bool, notify=changed)
    def ready(self):
        return bool(self._picked()) and bool(self._shapes) and not self._busy

    def _picked(self):
        return next((ln for ln in self._lines if ln["id"] == self._line and ln["file"]), None)

    # ---- the sheet's doors -----------------------------------------------------------------------------------
    @Slot(result=bool)
    def start(self):
        """Open on the selected swap set: the lines (the first made one picked) and the guessed shapes."""
        sel = self.b.selected_layers()
        item = self.b.doc.item(sel[0]) if len(sel) == 1 else None
        if not item or not item.get("swap"):
            self.b._set_status("Lip sync needs one swap set of mouth drawings selected.")
            return False
        try:
            self._lines = rig_voice.lines(self.b.doc.folder)
        except Exception as e:  # noqa: BLE001  Sound missing or a song that can't be read: said, the sheet stays shut
            return self.b._fail(f"Error: Lip sync: the project's voice lines can't be read: {e}") or False
        self._set, self._shapes = item["id"], rig_mouths.guess(item.get("layers", []))
        self._line = next((ln["id"] for ln in self._lines if ln["file"]), "")
        self.changed.emit()
        self.opened.emit()
        return True

    @Slot(str)
    def pickLine(self, line_id):
        self._line = line_id
        self.changed.emit()

    @Slot(str, str)
    def setShape(self, shape, layer):
        """Fix a guess: this mouth shape shows that drawing ("" = the nearest shape given)."""
        if layer:
            self._shapes[shape] = layer
        else:
            self._shapes.pop(shape, None)
        self.changed.emit()

    @Slot()
    def apply(self):
        line = self._picked()
        if not line or self._busy:
            return
        if rig_voice.heard(line):
            return self._after(None)
        self._busy = True
        self.changed.emit()

        def listen():
            from rostrum2d.lipsync import phonemes
            try:
                phonemes.analyse(line["file"], 0.0, None, line["text"] if line["english"] else None, "english")
                self._heard.emit(None)
            except Exception as e:  # noqa: BLE001  handed back to the screen's thread, said there
                self._heard.emit(e)
        threading.Thread(target=listen, name="lipsync-listen", daemon=True).start()

    def _after(self, error):
        self._busy = False
        line = self._picked()
        if error is not None or not line or not self._set:
            self.changed.emit()
            return self.b._fail(f"Error: Lip sync: {error}") if error is not None else None
        args = {"source": line["file"], "at": line["at"], **({"text": line["text"]} if line["english"] else {}),
                **{f"shape{s}": lay for s, lay in self._shapes.items()}}
        call = {"op": "lipsync.apply", "target": [self._set], "args": args}
        if self.b.guard(lambda: self.b._apply([call], f'Lip sync "{line["text"][:30]}"')):
            self.close()

    @Slot()
    def close(self):
        self._set, self._busy = "", False
        self.changed.emit()
