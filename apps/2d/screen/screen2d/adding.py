"""The Add menu: new layers from the screen, through the operations agents use (`layer.add` + the type's field operation).

One list everywhere (the rail's flyouts, Ctrl+K), most important first, and only what makes something you can see now:
a 3D render layer only when the project has a rendered 3D item to show (one entry per item, the layer set to it), never
an empty one. A new layer lands centred in the composition, is selected, and is one undo step. Path = the pen tool (the
path is made by its clicks); a drawing turns the Draw tool on; image and video ask for a file in QML and come back
through `addFile` (the same code as `run_import`).
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum2d import KIND, fields as F, render3d
from rostrum2d.io import importing
from rostrum_core import ids
from rostrum_core.tree import index

ENTRIES = ["shape", "text", "path", "image", "video", "drawing", "camera", "render3d"]      # new content only: groups and rigs are made from a selection (actions.py)
ASKS_FILE = ("image", "video")


def entries(folder=None) -> list[dict]:
    """The Add menu's entries that make something now: [{type, label}], a 3D render one per rendered 3D item of the
    project ({type, label: its name, item}); none without one."""
    out = []
    for t in ENTRIES:
        if t == "render3d":
            out += [{"type": t, "label": it["name"], "item": it["id"]} for it in render3d.placeable(folder)]
        else:
            out.append({"type": t, "label": F.LABELS[t]})
    return out


def lower(label: str) -> str:
    """A layer kind's name inside a sentence ("Add 3D render"): lower case, but 3D stays 3D."""
    return label.lower().replace("3d", "3D")


def new_layer_calls(doc, comp: dict, type_: str, more: dict | None = None) -> tuple[list[dict], str]:
    """layer.add + the type's field op placing it at the composition's centre (a camera has its own view, not placed);
    `more`: other fields set in the same call (a 3D render's item)."""
    lid = ids.counted(index(doc.data, KIND.lists), type_)
    calls = [{"op": "layer.add", "target": [comp["id"]], "args": {"type": type_, "id": lid}}]
    if type_ != "camera":
        args = {"x": comp["width"] / 2, "y": comp["height"] / 2}
        if type_ == "text":                     # a first text reads at about 8 % of the picture's height, in round steps of 4
            args["size"] = max(8, round(comp["height"] * 0.08 / 4) * 4)
        args.update(more or {})
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
        """[{type, label, item?}] (entries() for this project; read again by `refresh`)."""
        return entries(self.b.doc.folder if self.b.doc else None)

    @Slot()
    def refresh(self):
        """Read the project again (a 3D render may have landed): the rail calls it as the Media flyout opens."""
        self.changed.emit()

    @Slot(str)
    def add(self, type_):
        """The menu's entry: image / video ask for a file; path starts the pen; the rest add a layer now (a drawing
        also turns the Draw tool on). A 3D render: `render3d:<item>`, set to that item's render."""
        type_, _, item = type_.partition(":")
        if not any(e["type"] == type_ and e.get("item", item) == item for e in self.entries):
            have = ", ".join(e["type"] + (":" + e["item"] if "item" in e else "") for e in self.entries)
            return self.b._fail(f"Error: add: {type_}{':' + item if item else ''} is not in the Add menu ({have}).")
        if type_ in ASKS_FILE:
            self.fileWanted.emit(type_)
        elif type_ == "path":
            self.b.pen.setOn(True)
        else:
            more = {"item": item} if item else None
            if self._apply(lambda: new_layer_calls(self.b.doc, self.b.comp(), type_, more)[0], f"Add {lower(F.LABELS[type_])}")                     and type_ == "drawing":
                self.b.setTool("draw")

    def commands(self) -> list[dict]:
        """Ctrl+K's Add commands: the same entries, each doing what its menu entry does. A picture, video and the other
        files are one command, "Add from a file…" (the rail's one door, Ctrl+I)."""
        out = [{"key": "add:file", "label": "Add from a file…", "hint": "Document", "keys": "Ctrl+I",
                "words": "add new layer picture video image svg lottie pdf psd import", "do": lambda: self.fileWanted.emit("file")}]
        return out + [{"key": "add:" + e["type"] + (":" + e["item"] if "item" in e else ""),
                       "label": "Add " + (lower(F.LABELS["render3d"]) + ": " + e["label"] if "item" in e else lower(e["label"])),
                       "hint": "Document", "words": "add new layer " + e["type"],
                       "do": (lambda k=e["type"] + (":" + e["item"] if "item" in e else ""): self.add(k))}
                      for e in self.entries if e["type"] not in ASKS_FILE]

    @Slot(str, str)
    def addFile(self, type_, url):
        """An image or video picked in the dialog (a file:// url or a path): one layer, centred, selected. The file is
        copied into the project like Import's (media/), so no layer depends on a file outside it."""
        path = Path(QUrl(url).toLocalFile() if url.startswith("file:") else url)
        self._apply(lambda: importing.media_calls(self.b.doc.data, self.b.comp(), self.b.comp_id, type_, path,
                                                      folder=Path(self.b.doc.folder) if self.b.doc.folder else None), f"Add {type_}")

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
