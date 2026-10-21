"""The Add menu, Delete and Duplicate: new things from the screen, through the operations agents use (`mesh.add`,
`light.add`, `camera.add`, `group.add`, `material.add`, `shot.add`, `item.remove`, `material.remove`, `shot.remove`,
`item.duplicate`). Each is one undo step; the new thing is selected.

The menu offers only what applies now, most important first (a shot needs a camera, so Shot is absent until there is
one). A new item goes into the selected group or import (or the group holding the selected item), else the top level.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import ids
from rostrum_core.tree import index
from rostrum3d import fields as F
from rostrum3d.kind import KIND

LIGHT_NAMES = {"rect": "Rect panel", "disk": "Disk panel", "sphere": "Sphere bulb", "distant": "Sun", "dome": "Sky dome"}
START = {"camera": {"z": 5}, "light": {"y": 3}}          # where a new camera / light starts (an item starts at the origin)
REMOVE = {**dict.fromkeys(F.ITEMS, "item.remove"), "part": "item.remove", "material": "material.remove", "shot": "shot.remove"}
COPIES = (*F.ITEMS, "material", "shot")


def _entries(cameras: bool) -> list[dict]:
    out = [{"value": f"mesh:{s}", "label": f"Mesh · {s.capitalize()}"} for s in F.SHAPES]
    out += [{"value": f"light:{k}", "label": f"Light · {LIGHT_NAMES[k]}"} for k in F.LIGHT_KINDS]
    out += [{"value": t, "label": F.LABELS[t]} for t in ("camera", "group", "material")]
    return out + ([{"value": "shot", "label": "Shot"}] if cameras else [])


class Adder(QObject):
    changed = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b = bridge
        bridge.docChanged.connect(self.changed)
        bridge.selectionChanged.connect(self.changed)

    # ---- what the screen shows ----------------------------------------------------------------------------------
    @Property("QVariantList", notify=changed)
    def entries(self):
        return _entries(any(i.get("type") == "camera" for i in self.b.doc.items()))

    @Property(str, notify=changed)
    def selectedType(self):
        """"" when nothing is selected or the selection can be neither deleted nor copied (a key, nothing)."""
        t = self.b.doc.item(self.b.selected)["type"] if self.b.selected else ""
        return t if t in REMOVE else ""

    @Property(bool, notify=changed)
    def canDelete(self):
        """The shot the screen shows can't be deleted from under it (no Delete button for it)."""
        return self.selectedType != "" and self.b.selected != self.b.shot_id

    @Property(bool, notify=changed)
    def canDuplicate(self):
        return self.selectedType in COPIES

    # ---- the actions ---------------------------------------------------------------------------------------------
    @Slot(str)
    def add(self, choice):
        type_, _, detail = choice.partition(":")
        if choice not in [e["value"] for e in self.entries]:
            return self.b.fail_line(f"Error: add: {choice!r} is not in the Add menu right now.")
        new = ids.counted(index(self.b.doc.data, KIND.lists), type_)
        args = {"id": new, **START.get(type_, {})}
        if type_ == "mesh":
            args["shape"] = detail
            args["name"] = detail.capitalize()
        elif type_ == "light":
            args["kind"] = detail
            args["name"] = LIGHT_NAMES[detail]
        elif type_ == "shot":
            args["camera"] = self._camera()
        if type_ in F.ITEMS and (into := self._holder()):
            args["into"] = into
        self._apply([{"op": f"{type_}.add", "args": args}], f"Add {F.LABELS[type_].lower()}", new)

    @Slot()
    def duplicate(self):
        t = self.selectedType
        if t not in COPIES:
            return self.b.fail_line("Error: duplicate: select a scene item, material or shot first.")
        new = ids.counted(index(self.b.doc.data, KIND.lists), t)
        self._apply([{"op": "item.duplicate", "target": [self.b.selected], "args": {"id": new}}], f"Duplicate {t}", new)

    @Slot()
    def remove(self):
        t = self.selectedType
        if not t:
            return self.b.fail_line("Error: delete: select a scene item, material or shot first.")
        if not self.canDelete:
            return self.b.fail_line(f'Error: delete: "{self.b.shot_id}" is the shot this screen shows; open another shot first.')
        self._apply([{"op": REMOVE[t], "target": [self.b.selected]}], f"Delete {t}", "")

    # ---- inside --------------------------------------------------------------------------------------------------
    def _camera(self) -> str:
        sel = self.b.selected and self.b.doc.item(self.b.selected)
        if sel and sel["type"] == "camera":
            return sel["id"]
        return next(i["id"] for i in self.b.doc.items() if i.get("type") == "camera")

    def _holder(self) -> str:
        """The group or import a new item goes into: the selected one, or the one holding the selected item."""
        if not self.b.selected:
            return ""
        item = self.b.doc.item(self.b.selected)
        if item["type"] in F.HOLDERS:
            return item["id"]
        parent = self.b.doc.parent_of(item["id"])[0]
        return parent if parent != self.b.doc.data["id"] and self.b.doc.item(parent)["type"] in F.HOLDERS else ""

    def _apply(self, calls, label, select):
        def go():
            self.b._done(self.b.doc.apply(calls, self.b.who, label=label), "")
            if select:
                self.b.select(select)
        self.b._guard(go)
