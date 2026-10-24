"""The Library drawer's Paintings section (painted fill, DESIGN § 3.2, 3.9, 4): the scene's paintings as rows (a small picture,
the name, one line: "Seamless · 128 × 128 · 3 uses"), and what a person does with them: click = use it on the selection (with
nothing picked: pick its uses), the row's ↗ button = open it, right-click = Use / Open / Rename / Duplicate / Delete, "+ New painting",
"+ From <layer>'s paint". Offered to QML as `backend.library.paintings`. Paintings belong to the scene (the document), so the
section shows with or without a project. Each action is one change made by the same operations an agent calls
(layer.fill, painting.add / set / duplicate / remove), so one Ctrl+Z takes it back.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum2d import drawing, paintings
from rostrum2d.names import display_name
from rostrum2d.ops_painting import FILLABLE, why_not_from

_MAKE = ThreadPoolExecutor(max_workers=1, thread_name_prefix="painting-pictures")


def _plural(n: int, what: str) -> str:
    return f"{n} {what}" if n == 1 else f"{n} {what}s"


def line_of(p: dict, uses: int) -> str:
    """The small line under a painting's name."""
    n = len(p.get("frames", []))
    parts = (["Seamless"] if p.get("seamless") else []) + \
            [f"{n} drawings" if p.get("eachFrame") and n >= 2 else f'{p.get("w", 0)} × {p.get("h", 0)}']
    return " · ".join(parts + [_plural(uses, "use") if uses else "not used"])


class PaintingLibrary(QObject):
    changed = Signal()
    _made = Signal(bool)            # a picture was made on the worker (heard on the screen's thread)

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b, self._open, self._told, self._busy, self._rows = bridge, False, None, False, []
        bridge.docChanged.connect(self._check)
        bridge.selectedItemsChanged.connect(self._check)
        self._made.connect(self._after_picture)

    # ---- what is shown ---------------------------------------------------------------------------------------------
    def setOpen(self, on: bool):
        self._open = bool(on)
        self._told = None
        self._check()

    def _row(self, p: dict, jobs: list) -> dict:
        uses = len(paintings.uses(self.b.doc.data, p["id"]))
        frames = drawing.shown_frames(p)
        pic = drawing.picture(p, frames[0], later=jobs) if frames else None
        return {"id": p["id"], "name": p.get("name", "Painting"), "line": line_of(p, uses), "seamless": bool(p.get("seamless")),
                "picture": QUrl.fromLocalFile(str(pic)).toString() if pic else ""}

    def _check(self):
        """An edit or a selection: announced only when a row, or what the selection can do, really changed."""
        if not self._open:
            return
        jobs: list = []
        rows = [self._row(p, jobs) for p in paintings.all_of(self.b.doc.data)]
        if jobs and not self._busy:
            self._busy = True
            _MAKE.submit(self._make, jobs)
        told = (rows, len(self.takers()), self.maker_name())
        if told != self._told:
            self._told, self._rows = told, rows
            self.changed.emit()

    def _make(self, jobs):
        try:
            for job in jobs:
                job()
            self._made.emit(True)
        except Exception as e:  # noqa: BLE001  said on screen: a picture that can't be made is never a silent blank
            self._busy = False
            self.b._fail(f"Error: a painting's picture could not be made: {e}")

    def _after_picture(self, _ok):
        self._busy = False
        self._check()

    def takers(self) -> list[str]:
        """The picked layers that can take a painted fill: shapes and paths that are not locked."""
        out = []
        for i in self.b.selected_layers():
            it = self.b.doc.item(i)
            if it["type"] in FILLABLE and not it.get("locked"):
                out.append(i)
        return out

    def maker(self) -> dict | None:
        """The one picked layer a painting can be made from (its own paint, or a drawing), else None."""
        ids = self.b.selected_layers()
        item = self.b.doc.item(ids[0]) if len(ids) == 1 else None
        return item if item is not None and why_not_from(item) is None else None

    def maker_name(self) -> str:
        item = self.maker()
        return display_name(item) if item else ""

    rows = Property("QVariantList", lambda self: self._rows, notify=changed)
    canUse = Property(int, lambda self: len(self.takers()) if self._open else 0, notify=changed)   # layers a click would fill
    makerName = Property(str, lambda self: self.maker_name() if self._open else "", notify=changed)

    @Property(bool, notify=changed)
    def shown(self):
        """The section shows when the scene has a painting or what is picked can make one (like Colours)."""
        return bool(self._rows) or bool(self.maker_name())

    # ---- what a person does ----------------------------------------------------------------------------------------
    def _name(self, pid: str) -> str:
        return self.b.doc.item(pid).get("name", "Painting")

    def _fit(self, layer_id: str) -> str:
        """A layer that already has a painted fill keeps how it sits; any other starts stretched (as painting.add's `onto`)."""
        it = self.b.doc.item(layer_id)
        return it.get("fillFit", "stretch") if it.get("fillType") == "painted" else "stretch"

    @Slot(str)
    def use(self, pid: str):
        """Click: the painting is the fill of every picked shape and path (one change). With nothing picked: its uses are picked."""
        picked = self.b.selected_layers()
        name = self._name(pid)
        if not picked:
            users = [u["id"] for u in paintings.uses(self.b.doc.data, pid)]
            return self.b.selectMany(users) if users else self.b._set_status(f"{name} is not used yet: pick a shape first")
        ids = self.takers()
        if not ids:
            return self.b._set_status(f"{name} can't fill what is picked: only shapes and paths (not locked) take a painted fill")
        calls = [{"op": "layer.fill", "target": [i], "args": {"type": "painted", "painting": pid, "fit": self._fit(i)}} for i in ids]
        if self.b.guard(lambda: self.b._apply(calls, f"Use {name} on {_plural(len(ids), 'layer')}")):
            if len(ids) < len(picked):
                self.b._set_status(f"{name} is the fill of {_plural(len(ids), 'layer')}; {len(picked) - len(ids)} can't take it")

    @Slot(str)
    def open(self, pid: str):
        opened = getattr(self.b, "opened", None)         # the opened painting (painting_open.py)
        if opened is None:
            return self.b._set_status("Opening a painting on its own is not built yet")
        self.b.guard(lambda: opened.open(pid))

    @Slot(str, str)
    def rename(self, pid: str, name: str):
        name = name.strip()
        if name and name != self._name(pid):
            self.b.guard(lambda: self.b._apply([{"op": "painting.set", "target": [pid], "args": {"name": name}}], f"Rename {self._name(pid)}"))

    @Slot(str)
    def duplicate(self, pid: str):
        self.b.guard(lambda: self.b._apply([{"op": "painting.duplicate", "target": [pid]}], f"Duplicate {self._name(pid)}"))

    @Slot(str)
    def remove(self, pid: str):
        """One click, no question; the layers using it get a solid fill, and the top bar says how many. Ctrl+Z brings it all back."""
        name, n = self._name(pid), len(paintings.uses(self.b.doc.data, pid))
        if self.b.guard(lambda: self.b._apply([{"op": "painting.remove", "target": [pid]}], f"Delete {name}")):
            self.b._set_status(f"{name} deleted" + (f"; {_plural(n, 'layer')} now {'has' if n == 1 else 'have'} a solid fill" if n else ""))

    def _add(self, args: dict, label: str) -> str:
        """painting.add as one change; the new painting's id ("" when it was refused)."""
        before = {p["id"] for p in paintings.all_of(self.b.doc.data)}
        if not self.b.guard(lambda: self.b._apply([{"op": "painting.add", "args": args}], label)):
            return ""
        return next((p["id"] for p in paintings.all_of(self.b.doc.data) if p["id"] not in before), "")

    @Slot()
    def newPainting(self):
        """+ New painting: 512 × 512, seamless (a texture), opened on its own."""
        pid = self._add({}, "New painting")
        if pid:
            self.open(pid)

    @Slot()
    def fromPicked(self):
        """+ From <layer>'s paint: the picked layer's own paint (or a drawing's) becomes a painting."""
        item = self.maker()
        if item is None:
            return self.b._set_status("Pick one shape, path or drawing with paint of its own first")
        pid = self._add({"from": item["id"]}, f"New painting from {display_name(item)}")
        if pid:
            self.b._set_status(f"Made {self._name(pid)}")
