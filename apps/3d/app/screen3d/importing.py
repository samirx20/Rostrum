"""Importing from the screen (brief 29b), for QML as `backend.importer`: the rail's Import group (glTF / GLB, OBJ, FBX,
Alembic, USD, then Asset library), a file dragged from Explorer onto the viewport, and the unit message after.

A file picked in the Import group lands at once on the surface under the view's centre; a dropped file lands where it
was dropped. Both pick through the engine exactly as a click does (placing.py): a surface there → the import's base
(the bottom middle of its bounds) sits on the point hit; empty space → on the ground (y = 0) where the ray meets it;
no ground in sight (or very far off) → in front of the camera. One `import.add` per file, all in one undo step, the new
import selected, the tool back to Select (an armed shape is let go). The operation (ops_import.py) scales the file to
metres, stands a Z-up file upright and lists its parts (the scene list shows them under it, each with its own Material).

Rescaled on the way in: the status line says so once (`ops_import.unit_note`), and the selection's panel offers
*Keep original size* (`import.keep_size`, one undo step) for that import until the next edit (history.seq moves on).
The formats and their extensions come from `ops_import.FORMATS`; while that module is absent the group is absent.
"""
from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import Property, QObject, QUrl, Signal, Slot
from rostrum_core import ids
from rostrum_core.tree import index
from rostrum3d.kind import KIND

from . import placing

FAR = 50.0                  # a ground hit farther than this (metres, looking at the horizon) lands in front of the camera
AHEAD = (0.5, 20.0)         # in front of the camera: as far as the scene's middle is, kept within these


def _formats() -> list[dict]:
    try:
        from rostrum3d.ops_import import FORMATS
    except ImportError:
        return []
    return list(FORMATS)


def path_of(url_or_path: str) -> str:
    """A dialog's or a drop's file URL ("file:///C:/a.glb"), or a plain path, as a local path."""
    text = str(url_or_path)
    return QUrl(text).toLocalFile() if text.startswith("file:") else text


def importable(path: str) -> bool:
    ext = Path(path).suffix.lower()
    return any(ext in f["extensions"] for f in _formats())


def name_filter(fmt: dict) -> str:
    """The native dialog's filter for one format: "glTF / GLB (*.gltf *.glb)"."""
    return f'{fmt["label"]} ({" ".join("*" + e for e in fmt["extensions"])})'


def ahead(view, x, y) -> list[float]:
    """A point on the ray through picture px (x, y), as far from the eye as the world's middle is (within AHEAD)."""
    ray = view.ray(x, y)
    d = min(max(math.dist(view.eye, (0.0, 0.0, 0.0)), AHEAD[0]), AHEAD[1])
    return [e + r * d for e, r in zip(view.eye, ray)]


def landing(hit: dict, view, x, y) -> list[float]:
    """Where an import's base lands for an engine pick answer `hit` at picture px (x, y): the surface point hit, else
    the ground, else in front of the camera."""
    if hit.get("hit"):
        return list(hit["point"])
    ground = placing.ground_hit(view, x, y)
    if ground is not None and math.dist(ground[0], view.eye) <= FAR:
        return ground[0]
    return ahead(view, x, y)


class Importer(QObject):
    changed = Signal()
    answered = Signal(object)            # (files, pick answer or error line, scene, request) from the engine thread

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b = bridge
        self._keep, self._note, self._seq = "", "", -1        # the import Keep original size is offered for
        self.answered.connect(self._land)
        bridge.docChanged.connect(self._on_doc)

    # ---- what the screen shows ----------------------------------------------------------------------------------
    @Property("QVariantList", notify=changed)
    def rail(self):
        """The Import group's entries (Rail3D.qml): one per format, then Asset library while its sheet exists. Empty
        while the import operations aren't there (the group is absent)."""
        fmts = _formats()
        out = [{"name": f["label"] + "…", "icon": "import", "kind": "", "act": f"import:{f['name']}",
                "help": f"Bring in a {f['label']} file: it lands on the surface in the middle of the view."} for f in fmts]
        if fmts and getattr(self.b, "assets", None) is not None:
            out.append({"name": "Asset library", "icon": "library", "kind": "", "act": "import:library",
                        "help": "Models from the asset sources you turned on."})
        return out

    @Property("QVariantList", constant=True)
    def extensions(self):
        """Every extension a dropped file may have (".glb", ".usdz" …)."""
        return [e for f in _formats() for e in f["extensions"]]

    @Property(str, notify=changed)
    def keepFor(self):
        """The import that may still go back to its file's own size ("" = none): the panel's chip shows for it."""
        return self._keep

    @Property(str, notify=changed)
    def keepNote(self):
        return self._note

    # ---- the actions ---------------------------------------------------------------------------------------------
    @Slot(str, result="QVariantList")
    def nameFilters(self, name):
        fmt = next((f for f in _formats() if f["name"] == name), None)
        return [name_filter(fmt)] if fmt else []

    @Slot(str, result=str)
    def label(self, name):
        return next((f["label"] for f in _formats() if f["name"] == name), name)

    @Slot()
    def openLibrary(self):
        assets = getattr(self.b, "assets", None)
        if assets is None:
            return self.b.fail_line("Error: import: the asset library isn't here yet.")
        assets.open()

    @Slot(str)
    def importAtCentre(self, url):
        """A file picked in the Import group: onto the surface under the view's centre."""
        size = self._view_size()
        if size is not None:
            self._pick([url], size[0] / 2, size[1] / 2)

    @Slot("QVariantList", float, float)
    def dropAt(self, urls, x, y):
        """Files dropped on the viewport at (x, y) device pixels: the ones 3D can bring in land there."""
        files = [p for p in (path_of(u.toString() if isinstance(u, QUrl) else u) for u in urls) if importable(p)]
        if not files:
            return self.b.fail_line("Error: import: none of these files can be brought in "
                                    "(glTF, GLB, OBJ, FBX, Alembic or USD can).")
        if self._view_size() is not None:
            self._pick(files, x, y)

    @Slot()
    def keepSize(self):
        """Keep original size: the chip's import back to its file's own numbers (one undo step)."""
        target = self._keep
        if not target or not self.b.doc.has(target):
            return
        self._set_keep("", "")
        self.b._guard(lambda: self.b._done(self.b.doc.apply(
            [{"op": "import.keep_size", "target": [target]}], self.b.who, label="Keep original size"), ""))

    # ---- inside --------------------------------------------------------------------------------------------------
    def _view_size(self):
        v = self.b.viewport
        if v is None or v._size is None:
            self.b.fail_line("Error: import: the viewport isn't drawn yet; try again in a moment.")
            return None
        return v._size

    def _pick(self, urls, x, y):
        files = [path_of(u) for u in urls]
        missing = [f for f in files if not Path(f).is_file()]
        if missing:
            return self.b.fail_line(f"Error: import: {missing[0]} is not there.")
        v = self.b.viewport
        scene, req = v._pick_at(x, y)

        def job(eng):
            try:
                eng.ensure_scene(scene)
                self.answered.emit((files, eng.pick(**req), scene, req))
            except Exception as e:                          # loud, on the status line (never a silent no-op)
                self.answered.emit((files, str(e), scene, req))
        v._r.call(job)

    def _land(self, answer):
        files, hit, scene, req = answer
        if isinstance(hit, str):
            return self.b.fail_line(f"Error: import: {hit}")
        from .gizmo import View
        view = View.of(req, scene, self.b.frame, req["width"], req["height"])
        self.b._guard(lambda: self._add(files, landing(hit, view, req["x"], req["y"])))

    def _add(self, files, point):
        b, add = self.b, self.b.add
        add.disarm()                                       # a shape waiting for its click is let go: the tool is Select
        v = b.viewport
        for tool in (v.pose_tool, v.clay_tool, v.paint):    # (Pose, Clay, Paint end as V would end them)
            if tool.on:
                tool.leave()
        into = self._group()
        moved = placing.into_parent({"x": point[0], "y": point[1], "z": point[2]}, add._world(into))
        at = {k: moved[k] for k in "xyz"}                  # where its base lands; no turn (a Z-up file stands itself up)
        taken, made, calls = index(b.doc.data, KIND.lists), [], []
        for f in files:
            new = ids.counted(taken, "import", reserved=made)
            made.append(new)
            calls.append({"op": "import.add", "args": {"id": new, "name": Path(f).stem, "file": f, **at,
                                                       **({"into": into} if into else {})}})
        label = f"Import {Path(files[0]).name}" if len(files) == 1 else f"Import {len(files)} files"
        b._done(b.doc.apply(calls, b.who, label=label), "")
        if not b.doc.has(made[-1]):
            return
        b.select(made[-1])
        self._tell(made[-1])

    def _group(self) -> str:
        """The group a new import goes into: the selected group, or the group holding the selection; never another
        import (a file dropped while an import is selected is a thing of its own, not a piece of that file)."""
        doc, here = self.b.doc, self.b.selected
        while here and here != doc.data["id"]:
            if doc.item(here)["type"] == "group":
                return here
            here = doc.parent_of(here)[0]
        return ""

    def _tell(self, new):
        """The unit message, once, and Keep original size offered for this import."""
        try:
            from rostrum3d.ops_import import unit_note
        except ImportError:
            return
        note = unit_note(self.b.doc.item(new))
        if note:
            self.b.say(note)
            self._seq = self.b.doc.history.seq
            self._set_keep(new, note)

    def _on_doc(self, *_):
        if self._keep and (self.b.doc.history.seq != self._seq or not self.b.doc.has(self._keep)):
            self._set_keep("", "")                         # another edit (or undo): the offer is over

    def _set_keep(self, id_, note):
        if (id_, note) != (self._keep, self._note):
            self._keep, self._note = id_, note
            self.changed.emit()
