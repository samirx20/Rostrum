"""The Poses flyout (SPEC §9, Animate rail › Poses, P), for QML as `backend.poses`: Save pose from the selection,
the saved poses listed; click one = keys at the playhead for every field it holds; Shift+click = a breakdown,
halfway between the neighbouring keys. Every action is one operation agents call too (rostrum3d/ops_poses.py),
one undo step each.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot

from rostrum3d import fields as F

from . import pose_thumbs

BREAKDOWN = 0.5          # Shift+click: halfway between the neighbouring keys


class Poses(QObject):
    changed = Signal()

    def __init__(self, bridge):
        super().__init__(bridge)
        self.b = bridge
        bridge.docChanged.connect(self.changed)
        bridge.selectedItemsChanged.connect(self.changed)

    def _scene_selection(self) -> list[str]:
        return [i for i in self.b.selection if self.b.doc.has(i) and self.b.doc.item(i).get("type") in F.ITEMS]

    @Property("QVariantList", notify=changed)
    def saved(self):
        """[{id, name, holds, thumb}] of the saved poses; `holds` says what it keys ("lid, bud_1 · 6 settings"), `thumb`
        is its small picture's file URL ("" for none: pose_thumbs.py)."""
        out = []
        for p in self.b.doc.data.get("poses", []):
            items = list(dict.fromkeys(f.rpartition(".")[0] for f in p["fields"]))
            out.append({"id": p["id"], "name": p.get("name") or p["id"], "thumb": pose_thumbs.url(self.b.doc, p["id"]),
                        "holds": f"{', '.join(items[:3])}{' …' if len(items) > 3 else ''} · {len(p['fields'])} settings"})
        return out

    @Property(bool, notify=changed)
    def canSave(self):
        return bool(self._scene_selection())

    def _run(self, call, label):
        self.b._guard(lambda: self.b._done(self.b.doc.apply([call], self.b.who, label=label), ""))

    @Slot(str)
    def save(self, name):
        """A pose of the selected items as they are at the playhead, named `name` ("" = counted: Pose 3)."""
        targets = self._scene_selection()
        if not targets:
            return self.b.fail_line("Error: save pose: select the items the pose should hold first.")
        args = {"at": self.b.time, **({"name": name.strip()} if name.strip() else {})}
        before = {p["id"] for p in self.b.doc.data.get("poses", [])}
        self._run({"op": "pose.save", "target": targets, "args": args}, "Save pose")
        new = [p["id"] for p in self.b.doc.data.get("poses", []) if p["id"] not in before]
        if new and self.b.viewport is not None:       # the picture on screen now is the pose's thumbnail
            pose_thumbs.save(self.b.doc, new[0], self.b.viewport.provider.requestImage("", None, None))
            self.changed.emit()

    @Slot(str, bool)
    def apply(self, pose_id, breakdown=False):
        """Key the pose at the playhead; `breakdown` (Shift+click): halfway between the neighbouring keys instead."""
        args = {"at": self.b.time, **({"share": BREAKDOWN} if breakdown else {})}
        self._run({"op": "pose.apply", "target": [pose_id], "args": args}, "Breakdown" if breakdown else "Apply pose")

    @Slot(str, str)
    def rename(self, pose_id, name):
        if name.strip():
            self._run({"op": "pose.rename", "target": [pose_id], "args": {"name": name.strip()}}, "Rename pose")

    @Slot(str)
    def remove(self, pose_id):
        self._run({"op": "pose.remove", "target": [pose_id]}, "Delete pose")
