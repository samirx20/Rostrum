"""Lip sync… (UX_SPEC 3.23; qml/RostrumKit/LipSyncSheet.qml, one sheet for 2D and 3D): the project's voice lines (from
RostrumSound, rostrum_core.lipsync.voice), a row per mouth shape with the drawing / mesh guessed from its name (pick
another to fix a wrong guess), Apply = one change. A line not heard before is listened to first, off the screen's
thread (the phone model: a few seconds to a minute); the sheet says so and Apply waits, then makes the one change.

The app gives a host (duck-typed; the app's bridge is behind it):
    host.folder                          the project folder
    host.mouth() -> None | (id, label, [(child id, child name), ...])    the selected mouth, or None (it says why itself)
    host.apply(mouth id, line, shapes)   make the one change (an operation); True when it went through
    host.fail(line)                      say a failure loudly
`line` is a rostrum_core.lipsync.voice.lines entry; `shapes` {shape: child id}.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core.lipsync import mouths, phonemes, voice


class LipSyncSheet(QObject):
    changed = Signal()
    opened = Signal()
    _heard = Signal(object)             # an error, or None when the line's phones are in the cache

    def __init__(self, host, parent=None):
        super().__init__(parent)
        self.h = host
        self._set, self._label, self._kids, self._lines, self._line, self._shapes, self._busy = "", "", [], [], "", {}, False
        self._heard.connect(self._after)

    @Property(bool, notify=changed)
    def open(self):
        return bool(self._set)

    @Property(str, notify=changed)
    def what(self):
        return self._label

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
        if line and not voice.heard(line):
            out += "Apply listens to this line first (a few seconds to a minute)."
        return out.strip()

    @Property("QVariantList", notify=changed)
    def rows(self):
        return mouths.rows(self._kids, self._shapes) if self._set else []

    @Property(bool, notify=changed)
    def ready(self):
        return bool(self._picked()) and bool(self._shapes) and not self._busy

    def _picked(self):
        return next((ln for ln in self._lines if ln["id"] == self._line and ln["file"]), None)

    # ---- the sheet's doors -----------------------------------------------------------------------------------
    @Slot(result=bool)
    def start(self):
        """Open on the selected mouth: the lines (the first made one picked) and the guessed shapes."""
        mouth = self.h.mouth()
        if not mouth:
            return False
        try:
            self._lines = voice.lines(self.h.folder)
        except Exception as e:  # noqa: BLE001  Sound missing or a song that can't be read: said, the sheet stays shut
            return self.h.fail(f"Error: Lip sync: the project's voice lines can't be read: {e}") or False
        self._set, self._label, self._kids = mouth[0], mouth[1], list(mouth[2])
        self._shapes = mouths.guess(self._kids)
        self._line = next((ln["id"] for ln in self._lines if ln["file"]), "")
        self.changed.emit()
        self.opened.emit()
        return True

    @Slot(str)
    def pickLine(self, line_id):
        self._line = line_id
        self.changed.emit()

    @Slot(str, str)
    def setShape(self, shape, child):
        """Fix a guess: this mouth shape shows that child ("" = the nearest shape given)."""
        if child:
            self._shapes[shape] = child
        else:
            self._shapes.pop(shape, None)
        self.changed.emit()

    @Slot()
    def apply(self):
        line = self._picked()
        if not line or self._busy:
            return
        if voice.heard(line):
            return self._after(None)
        self._busy = True
        self.changed.emit()

        def listen():
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
            return self.h.fail(f"Error: Lip sync: {error}") if error is not None else None
        if self.h.apply(self._set, line, dict(self._shapes)):
            self.close()

    @Slot()
    def close(self):
        self._set, self._busy = "", False
        self.changed.emit()
