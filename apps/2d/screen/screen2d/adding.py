"""The Add menu: new layers from the screen, through the operations agents use (`layer.add` + the type's field operation).

What the menu offers depends on the page (only what applies, most important first; nothing greyed out). A new layer lands
centred in the composition, is selected, and is one undo step. Path = the pen tool (the path is made by its clicks); image and
video ask for a file in QML and come back through `addFile` (the same code as `run_import`).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum2d import KIND, fields as F
from rostrum2d.io import importing
from rostrum_core import ids
from rostrum_core.tree import index

ENTRIES = {
    "design": ["shape", "text", "path", "image", "video", "group", "camera"],
    "draw": ["drawing"],
    "animate": ["camera", "rig", "group"],
}
ASKS_FILE = ("image", "video")


def new_layer_calls(doc, comp: dict, type_: str) -> tuple[list[dict], str]:
    """layer.add + the type's field op placing it at the composition's centre (a camera has its own view, not placed)."""
    lid = ids.counted(index(doc.data, KIND.lists), type_)
    calls = [{"op": "layer.add", "target": [comp["id"]], "args": {"type": type_, "id": lid}}]
    if type_ != "camera":
        calls.append({"op": KIND.registry.field_op(type_).name, "target": [lid], "args": {"x": comp["width"] / 2, "y": comp["height"] / 2}})
    return calls, lid


class Adder(QObject):
    changed = Signal()
    fileWanted = Signal(str)              # image | video: QML opens the file dialog, then calls addFile

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b = bridge
        bridge.pageChanged.connect(self.changed)

    @Property("QVariantList", notify=changed)
    def entries(self):
        """[{type, label}] for the current page."""
        return [{"type": t, "label": F.LABELS[t]} for t in ENTRIES[self.b.page]]

    @Slot(str)
    def add(self, type_):
        """The menu's entry: image / video ask for a file; path starts the pen; the rest add a layer now."""
        if type_ not in ENTRIES[self.b.page]:
            return self.b._fail(f"Error: add: {type_} is not in the Add menu of the {self.b.page} page.")
        if type_ in ASKS_FILE:
            self.fileWanted.emit(type_)
        elif type_ == "path":
            self.b.pen.setOn(True)
        else:
            self._apply(lambda: new_layer_calls(self.b.doc, self.b.comp(), type_)[0], f"Add {F.LABELS[type_].lower()}")

    @Slot(str, str)
    def addFile(self, type_, url):
        """An image or video picked in the dialog (a file:// url or a path): one layer, centred, selected."""
        path = Path(QUrl(url).toLocalFile() if url.startswith("file:") else url)
        self._apply(lambda: importing.media_calls(self.b.doc.data, self.b.comp(), self.b.comp_id, type_, path), f"Add {type_}")

    def _apply(self, make, label):
        """One change (all the calls, or nothing); an error goes to the status line, never a half layer."""
        try:
            calls = make()
            self.b.done(self.b.doc.apply(calls, self.b.who, label=label), "")
            self.b.select(calls[0]["args"]["id"])
        except Exception as e:                      # a missing file, ffprobe, a refused operation: say what, don't crash
            self.b._fail(getattr(e, "line", lambda: f"Error: {label}: {e}")())
