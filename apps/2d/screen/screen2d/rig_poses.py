"""The pose library in the settings panel (UX_SPEC 3.23 › Pose library; `backend.poses`, qml/RigPoses.qml): with a rig
in hand, its saved poses as a list. Save pose keeps the pose at the playhead (`pose.save`); a click on a pose keys it
at the playhead (`pose.apply`, one change); its slider goes part of the way from the pose there now (`pose.apply
{amount}` previewed while dragging: one change on release); ⋯ › Rename (`item.rename`), Delete (`pose.remove`).
`shown`: only while a pose can apply, the rig or its bones picked (not a part with a bone: Attach to bone's
selection). Screen state only.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum2d.names import unique_name
from rostrum_gui.edits import Drag


class PoseList(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent)
        self.b, self._drag, self._blend = bridge, None, ("", 0.0)
        for sig in (bridge.rig.changed, bridge.docChanged, bridge.selectionChanged):
            sig.connect(self.changed)

    @Property(str, notify=changed)
    def rig(self):
        return self.b.rig.rig

    @Property(bool, notify=changed)
    def shown(self):
        """A rig in hand and nothing but it or its bones / IK handles picked: a pose applies to what is picked."""
        rig = self.b.rig.rig
        if not rig:
            return False
        item = self.b.doc.item(rig)
        posable = {rig} | {i["id"] for key in ("bones", "iks") for i in item.get(key, [])}
        return set(self.b._kit.selection) <= posable

    @Property("QVariantList", notify=changed)
    def poses(self):
        """{id, name, amount}: amount = the slider while it is dragged (1 otherwise)."""
        rig = self.b.rig.rig
        if not rig:
            return []
        return [{"id": p["id"], "name": p["name"], "amount": self._blend[1] if self._blend[0] == p["id"] else 1.0}
                for p in self.b.doc.item(rig).get("poses", [])]

    def _t(self):
        return round(self.b.own_t(self.b.rig.rig), 6)

    @Slot()
    def save(self):
        """Save pose: the rig's pose at the playhead, as "Pose 1", "Pose 2" … (rename it in its settings)."""
        rig = self.b.rig.rig
        if rig:
            name = unique_name({p["name"] for p in self.b.doc.item(rig).get("poses", [])}, "Pose")
            self.b.guard(lambda: self.b._apply([{"op": "pose.save", "target": [rig], "args": {"name": name, "t": self._t()}}],
                                              f"Save pose {name}"))

    @Slot(str)
    def apply(self, pose):
        """A click on a pose: key it at the playhead (one change)."""
        rig = self.b.rig.rig
        if rig:
            self.b.guard(lambda: self.b._apply([self._call(pose, 1.0)], f"Apply pose {self.b.doc.item(pose)['name']}"))

    def _call(self, pose, amount):
        return {"op": "pose.apply", "target": [self.b.rig.rig], "args": {"pose": pose, "t": self._t(), "amount": amount}}

    @Slot(str, float)
    def blendTo(self, pose, amount):
        """The pose's slider moved: that much of the way from the pose there now (previewed; one change on release)."""
        if self._drag is None:
            def go():
                self._drag = Drag(self.b.doc, self.b.who, f"Blend to {self.b.doc.item(pose)['name']}")
            if not self.b.guard(go):
                return
        self._blend = (pose, max(0.0, min(1.0, amount)))
        self.b.guard(lambda: self._drag.preview([self._call(pose, round(self._blend[1], 3))]))
        self.changed.emit()

    @Slot()
    def endBlend(self):
        d, self._drag, self._blend = self._drag, None, ("", 0.0)
        if d is not None:
            self.b.guard(lambda: self.b.done(d.end(), ""))
        self.changed.emit()

    @Slot(str, str)
    def rename(self, pose, name):
        self.b.guard(lambda: self.b._apply([{"op": "item.rename", "target": [pose], "args": {"name": name}}],
                                          f"Rename pose {name}"))

    @Slot(str)
    def remove(self, pose):
        self.b.guard(lambda: self.b._apply([{"op": "pose.remove", "target": [pose], "args": {}}], "Delete pose"))
