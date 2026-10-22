"""The Add menu: new layers from the screen, through the operations agents use (`layer.add` + the type's field operation).

One list everywhere, most important first (a 3D render only when Rostrum3D is installed: nothing greyed out). A new layer
lands centred in the composition, is selected, and is one undo step. Path = the pen tool (the path is made by its clicks);
a drawing turns the Draw tool on; image and video ask for a file in QML and come back through `addFile` (the same code as
`run_import`).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum2d import KIND, fields as F, settings
from rostrum2d.io import importing
from rostrum_core import ids
from rostrum_core.tree import index

ENTRIES = ["shape", "text", "path", "image", "video", "drawing", "camera", "render3d"]      # new content only: groups and rigs are made from a selection (actions.py)
ASKS_FILE = ("image", "video")
ONLY_WITH_3D = ("render3d",)            # a Rostrum3D item's render: offered only when Rostrum3D is installed


def entries() -> list[str]:
    """The Add menu's types that can be used here (no 3D render layer without Rostrum3D)."""
    has3d = settings.has_rostrum3d()
    return [t for t in ENTRIES if has3d or t not in ONLY_WITH_3D]


def new_layer_calls(doc, comp: dict, type_: str) -> tuple[list[dict], str]:
    """layer.add + the type's field op placing it at the composition's centre (a camera has its own view, not placed)."""
    lid = ids.counted(index(doc.data, KIND.lists), type_)
    calls = [{"op": "layer.add", "target": [comp["id"]], "args": {"type": type_, "id": lid}}]
    if type_ != "camera":
        args = {"x": comp["width"] / 2, "y": comp["height"] / 2}
        if type_ == "text":                     # a first text reads at about 8 % of the picture's height, in round steps of 4
            args["size"] = max(8, round(comp["height"] * 0.08 / 4) * 4)
        calls.append({"op": KIND.registry.field_op(type_).name, "target": [lid], "args": args})
    return calls, lid


class Adder(QObject):
    changed = Signal()
    fileWanted = Signal(str)              # image | video: QML opens the file dialog, then calls addFile

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b = bridge

    @Property("QVariantList", notify=changed)
    def entries(self):
        """[{type, label}]."""
        return [{"type": t, "label": F.LABELS[t]} for t in entries()]

    @Slot(str)
    def add(self, type_):
        """The menu's entry: image / video ask for a file; path starts the pen; the rest add a layer now (a drawing
        also turns the Draw tool on)."""
        if type_ not in entries():
            return self.b._fail(f"Error: add: {type_} is not in the Add menu ({', '.join(entries())}).")
        if type_ in ASKS_FILE:
            self.fileWanted.emit(type_)
        elif type_ == "path":
            self.b.pen.setOn(True)
        else:
            if self._apply(lambda: new_layer_calls(self.b.doc, self.b.comp(), type_)[0], f"Add {F.LABELS[type_].lower()}")                     and type_ == "drawing":
                self.b.setTool("draw")

    @Slot(str, str)
    def addFile(self, type_, url):
        """An image or video picked in the dialog (a file:// url or a path): one layer, centred, selected."""
        path = Path(QUrl(url).toLocalFile() if url.startswith("file:") else url)
        self._apply(lambda: importing.media_calls(self.b.doc.data, self.b.comp(), self.b.comp_id, type_, path), f"Add {type_}")

    def _apply(self, make, label) -> bool:
        """One change (all the calls, or nothing); an error goes to the status line, never a half layer."""
        try:
            calls = make()
            self.b.done(self.b.doc.apply(calls, self.b.who, label=label), "")
            self.b.select(calls[0]["args"]["id"])
            return True
        except Exception as e:                      # a missing file, ffprobe, a refused operation: say what, don't crash
            self.b._fail(getattr(e, "line", lambda: f"Error: {label}: {e}")())
            return False
