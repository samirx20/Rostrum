"""Copy, cut and paste of layers through the system clipboard (a slot mix-in for Bridge2D, see rostrum_gui/parts.py),
so it works between two windows or two projects. Copy puts the selected layers' data (rostrum2d.ops_clip.copied) on
the clipboard twice: under Rostrum2D's own type and as plain JSON text (an agent or a text editor can read it; paste
also takes that text back). Copy is not a change. Cut = copy + layer.remove (one change). Paste = layer.paste (one
change) into the selected layer's group, just above it (nothing selected: the top of the composition shown), then the
pasted layers are selected (Ctrl+Shift+V, `paste_other`, pastes layers the same way, in place; copied keys it pastes
at their original times: key_edits.py). Files copied in a file browser are imported; a Figma link opens Import on that
frame (`_paste_outside`: what came from outside Rostrum).
"""
from __future__ import annotations

import json

from PySide6.QtCore import Slot
from PySide6.QtGui import QGuiApplication
from rostrum2d import fields as F
from rostrum2d.io.figma import link_parts
from rostrum2d.ops_clip import copied
from rostrum_gui import clip
from rostrum_gui.parts import SlotMixin

MIME = "application/x-rostrum2d-layers"


class ClipboardSlots(SlotMixin):
    @Slot(result=bool)
    def copyLayers(self):
        """The selected layers onto the clipboard (nothing else changes)."""
        layers = self._clip_layers()
        if not layers:
            self._set_status("Nothing to copy: select a layer first")
            return False
        text = json.dumps(copied(self.doc.data, self.doc.kind.lists, layers))
        clip.put({MIME: text.encode("utf-8")}, text)
        self._key_clip = []                         # the latest copy wins: Ctrl+V pastes layers now (key_edits.py)
        self._set_status(f"Copied {self._clip_count(len(layers))}")
        return True

    @Slot(result=bool)
    def cutLayers(self):
        """Copy, then delete the selected layers (one change: Undo brings them back)."""
        layers = self._clip_layers()
        return bool(layers) and self.copyLayers() and self._guard(
            lambda: self._apply([{"op": "layer.remove", "target": layers, "args": {}}], f"Cut {self._clip_count(len(layers))}"))

    @Slot(result=bool)
    def pasteLayers(self):
        """What the clipboard holds, just above the selected layer (or on top of the composition), then selected."""
        text = self._clip_text()
        if not text:
            return self._paste_outside()
        into, at = self._clip_place()
        before = {layer["id"] for layer in self.doc.item(into).get("layers", [])}
        args = {"layers": text, "into": into, **({} if at is None else {"index": at})}
        n = len(json.loads(text))
        if not self._guard(lambda: self._apply([{"op": "layer.paste", "args": args}], f"Paste {self._clip_count(n)}")):
            return False
        self.selectMany([layer["id"] for layer in self.doc.item(into).get("layers", []) if layer["id"] not in before])
        return True

    def _clip_outside(self) -> bool:
        """The clipboard holds what _paste_outside takes: files copied in Explorer / Finder, or a Figma link. (Paste is
        offered for it too: the action's "clipboard" fact was layers only, so Ctrl+V on a link said it didn't fit.)"""
        mime = QGuiApplication.clipboard().mimeData()
        return mime is not None and (any(u.isLocalFile() for u in mime.urls()) or link_parts(mime.text() or "") is not None)

    def _paste_outside(self) -> bool:
        """From outside Rostrum, not layers: files copied in Explorer / Finder are imported (as if dropped, centred); a
        Figma link opens Import on Figma with the file and frame filled in (importer.py). Else nothing to paste, said."""
        mime = QGuiApplication.clipboard().mimeData()
        if mime is not None and mime.hasUrls() and any(u.isLocalFile() for u in mime.urls()):
            return self._importer.dropFiles([u.toString() for u in mime.urls() if u.isLocalFile()], float("nan"), float("nan"))
        if mime is not None and self._importer.takeLink(mime.text() or ""):
            self._importer.wantPanel.emit()
            return True
        self._set_status("Nothing to paste: copy a layer, a file or a Figma link first")
        return False

    def _clip_layers(self) -> list[str]:
        return [i for i in self.selection if self.doc.item(i)["type"] in F.LAYERS]

    @staticmethod
    def _clip_count(n: int) -> str:
        return "1 layer" if n == 1 else f"{n} layers"

    def _clip_text(self) -> str:
        """Rostrum2D's own data, else plain text that reads as a list of layers ("" = nothing pasteable)."""
        mime = QGuiApplication.clipboard().mimeData()
        if mime is None:
            return ""
        if mime.hasFormat(MIME):
            return bytes(mime.data(MIME)).decode("utf-8")
        try:
            data = json.loads(mime.text() or "null")
        except ValueError:
            return ""
        ok = isinstance(data, list) and data and all(isinstance(x, dict) and x.get("type") in F.LAYERS for x in data)
        return mime.text() if ok else ""

    def _clip_place(self):
        """(group or composition, index): just above the selected layer, else on top of the composition shown."""
        sel = self._clip_layers()
        if sel:
            parent, key, index = self.doc.parent_of(sel[0])
            if key == "layers":
                return parent, index + 1
        return self.comp_id, None
