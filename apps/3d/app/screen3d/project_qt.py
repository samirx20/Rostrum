"""Project a picture from <shot> on the screen (brief 21b), for QML as `projector`: right-click selected shapes ›
Project a picture from Hero 01… (actions3d.py) opens a short menu of what to project: each 2D item of the project
that has a pictures render (linked: re-rendering it in 2D updates the projection) and "A picture file…". The choice
is one change, `paint.project` on the selected meshes from the shown shot's camera: a paint layer on each that the
picture is laid on from that camera, so it keeps its place (and shows depth) when the view moves.

Linked 2D items are watched (every 2 s, only while the document links one): when one has a newer pictures render
(repainted and rendered in 2D), the viewport draws the scene again with it.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QTimer, QUrl, Signal, Slot
from rostrum_core import project

FILE = "file"


class Projector(QObject):
    asked = Signal("QVariantList")           # the menu's entries: QML opens it (ProjectPicture.qml)

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self._b, self._targets = bridge, []
        self._versions: dict[str, object] = {}
        self._watch = QTimer(self, interval=2000)
        self._watch.timeout.connect(self._check)
        self._watch.start()

    def _linked(self) -> set[str]:
        """The 2D items the document shows: projected pictures and glow from 2D."""
        out = set()
        for m in self._b.doc.data.get("materials", []):
            if m.get("emissionRender"):
                out.add(m["emissionRender"])
        stack = list(self._b.doc.data.get("items", []))
        while stack:
            it = stack.pop()
            stack += it.get("children", [])
            for p in it.get("paints", []):
                src = p.get("projectSource", "")
                if src.startswith("2d:"):
                    out.add(src[3:])
        return out

    def _check(self):
        folder = getattr(self._b.doc, "folder", None)
        if not folder:
            return
        changed = False
        for ref in self._linked():
            try:
                r = project.latest_render(folder, ref, "pictures")
            except Exception:  # noqa: BLE001  a missing item is said where the scene is compiled
                continue
            v = r and r.get("version")
            if ref in self._versions and self._versions[ref] != v:
                changed = True
            self._versions[ref] = v
        vp = getattr(self._b, "viewport", None)
        if changed and vp is not None:
            vp._on_doc()                       # compiled again: the newest render is laid on

    def entries(self) -> list[dict]:
        out = []
        folder = getattr(self._b.doc, "folder", None)
        if folder:
            for it in project.items(folder, "2d"):
                if project.latest_render(folder, it["id"], "pictures") is not None:
                    out.append({"value": f'2d:{it["id"]}', "label": f'{it.get("name") or it["id"]} (2D, follows it)',
                                "group": "2d"})
        return out + [{"value": FILE, "label": "A picture file…", "group": "file"}]

    def open(self, targets: list[str]) -> None:
        self._targets = [t for t in targets if self._b.doc.has(t)]
        self.asked.emit(self.entries())

    @Slot(str)
    def project(self, source: str) -> None:
        """Project `source` ("2d:<id>", a file path or file URL) onto the shapes the menu was opened for."""
        if source.startswith("file:"):
            source = QUrl(source).toLocalFile()
        targets = [t for t in self._targets if self._b.doc.has(t)]
        if not targets or not source:
            return
        shot = self._b.shot_info()
        what = Path(source).name if not source.startswith("2d:") else source[3:]
        calls = [{"op": "paint.project", "target": targets, "args": {"shot": shot["id"], "picture": source}}]
        self._b._guard(lambda: self._b._apply(calls, f'Project {what} from {shot.get("name") or shot["id"]}'))
