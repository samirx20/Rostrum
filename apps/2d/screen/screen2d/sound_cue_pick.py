"""Add a sound here… (UX_SPEC 3.28 Sync sound): one layer selected, in a project with sound → the action opens a small
popover listing sounds (Sound's library and the person's sound folders, read-only), with a search box; a click ties
that sound to the layer's start (rostrum2d/sound_cues.cue: the clip goes into Sound's song, timed by a marker that
follows the layer). The agents' edit_sound_cue runs the same function. Offered to QML as `backend.cuePick`.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d import sound_cues


class CuePick(QObject):
    changed = Signal()
    opened = Signal()               # QML opens the popover (the action's `do`)

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._layer, self._words, self._rows = bridge, "", "", []

    layer = Property(str, lambda self: self._layer, notify=changed)
    words = Property(str, lambda self: self._words, notify=changed)
    sounds = Property("QVariantList", lambda self: self._rows, notify=changed)

    @Property(str, notify=changed)
    def what(self):
        return self.b.label_of(self.b.doc.item(self._layer)) if self._layer and self.b.doc.has(self._layer) else ""

    @Slot(result=bool)
    def start(self):
        layers = self.b.selected_layers()
        if len(layers) != 1:
            self.b._set_status("Add a sound here: select one layer.")
            return False
        self._layer = layers[0]
        self.search(self._words)
        self.opened.emit()
        return True

    @Slot(str)
    def search(self, words):
        self._words = words
        try:
            self._rows = [{**r, "label": r["about"], "hint": f'{r["seconds"]:g} s · {r["where"]}' if r.get("seconds")
                           else r["where"]} for r in sound_cues.choices(words, 40)]
        except Exception as e:  # noqa: BLE001  the library can't be read: said, never an empty list passed off as none
            self._rows = []
            self.b._fail(e.line() if hasattr(e, "line") else f"Error: sounds: {e}")
        self.changed.emit()

    @Slot(str, result=bool)
    def pick(self, path):
        """Tie `path` to the layer: one change in Sound's song (and its marker), said in the status line."""
        if not self._layer:
            return False
        try:
            r = sound_cues.cue(self.b.doc.folder, self.b.doc, self._layer, path, self.b.who,
                               chosen=self.b.comp().get("soundtrack", ""))
        except Exception as e:  # noqa: BLE001  loud, in words
            self.b._fail(e.line() if hasattr(e, "line") else f"Error: Add a sound here: {e}")
            return False
        self.b._set_status(f'Added {Path(r["file"]).stem} at "{r["marker"]}" · RostrumSound mixes it')
        self._layer = ""
        self.changed.emit()
        return True
