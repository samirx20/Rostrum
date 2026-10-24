"""Adding, Delete and Duplicate: new things from the screen, through the operations agents use (`mesh.add`,
`light.add`, `camera.add`, `rig.add`, `group.add`, `material.add`, `shot.add`, `item.remove`, `material.remove`,
`shot.remove`, `item.duplicate`). Each is one undo step; the new thing is selected.

Where each is offered: the tool rail's Shapes, Lights and Camera flyouts (`rail`, SPEC §2), the header's Materials chip
(New material) and the shot crumb (New shot). Only what applies now (a shot needs a camera, so New shot is absent until
there is one). A new item goes into the selected group or import (or the group holding the selected item), else the top level.

A shape from the Shapes flyout is placed by clicking (SPEC §4.1): picking it *arms* it (`armed`), the next click in the
viewport places it on the surface under the pointer (`place_at`, maths in placing.py), and the tool is Select again;
Esc or a right-click lets go (`disarm`). Agents place with `mesh.add`'s x y z rx ry rz, or `place_on` in a script.
The Type & logo flyout's outlines (text, svg, path2d; SPEC §4.4) are armed with their source (`armWith`: the SVG file,
the 2D item and path layer) and stand upright facing the shot camera; 3D text then takes typing in place (type_in_place.py).
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum_core import ids
from rostrum_core.tree import index
from rostrum3d import fields as F
from rostrum3d import highlight as H
from rostrum3d.kind import KIND
from rostrum3d.outline_fields import OUTLINE_SHAPES

from . import placing
from .type_in_place import Typer

LIGHT_NAMES = {"rect": "Softbox", "disk": "Round softbox", "strip": "Strip", "sphere": "Bulb", "spot": "Spot", "distant": "Sun", "dome": "Sky"}
RAIL_SHAPES = ("box", "sphere", "cylinder", "cone", "torus", "capsule", "plane", "disc")   # SPEC §2's order
RAIL_TYPE = (("text", "3D text"), ("svg", "SVG logo"), ("path2d", "2D drawing"))   # Type & logo (T)
OUTLINE_NAMES = {"text": "Text", "svg": "Logo", "path2d": "Drawing"}          # a new outline's name (and the hint's word)
START = {"camera": {"z": 5}, "light": {"y": 3}}          # where a new camera / light starts (an item starts at the origin)
REMOVE = {**dict.fromkeys(F.ITEMS, "item.remove"), "part": "item.remove", "material": "material.remove", "shot": "shot.remove"}
COPIES = (*F.ITEMS, "material", "shot")


def _entries(cameras: bool) -> list[dict]:
    out = [{"value": f"mesh:{s}", "label": f"Mesh · {s.capitalize()}"} for s in F.SHAPES]
    out += [{"value": f"light:{k}", "label": f"Light · {LIGHT_NAMES.get(k, k.capitalize())}"} for k in F.LIGHT_KINDS]
    out += [{"value": t, "label": F.LABELS[t]} for t in ("camera", "rig", "group", "material")]
    return out + ([{"value": "shot", "label": "Shot"}] if cameras else [])


def _rail() -> dict:
    """The rail's flyouts, filled from today's add operations: {group: [{value (an add choice), name, icon}]}."""
    return {"shapes": [{"value": f"mesh:{s}", "name": s.capitalize(), "icon": s} for s in RAIL_SHAPES if s in F.SHAPES],
            "type": [{"value": f"mesh:{s}", "name": n, "icon": s} for s, n in RAIL_TYPE if s in F.SHAPES],
            "lights": [{"value": f"light:{k}", "name": LIGHT_NAMES.get(k, k.capitalize()), "icon": f"light-{k}"}
                       for k in F.LIGHT_KINDS],
            "camera": [{"value": "camera", "name": "Camera", "icon": "camera"},
                       {"value": "rig", "name": "Camera rig", "icon": "rig"}]}


class Adder(QObject):
    changed = Signal()
    armedChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b = bridge
        self._armed = ""                        # an add choice waiting for its click in the viewport ("" = none)
        self._extra = {}                        # its source fields (svgFile; doc2d + layer), given when armed
        self._typer = Typer(bridge, self)       # typing a placed 3D text in place
        bridge.docChanged.connect(self.changed)
        bridge.selectionChanged.connect(self.changed)

    # ---- what the screen shows ----------------------------------------------------------------------------------
    @Property("QVariantList", notify=changed)
    def entries(self):
        return _entries(any(i.get("type") == "camera" for i in self.b.doc.items()))

    @Property("QVariantMap", constant=True)
    def rail(self):
        return _rail()

    typer = Property(QObject, lambda s: s._typer, constant=True)        # typing a placed 3D text (type_in_place.py)

    @Property(bool, notify=changed)
    def canAddShot(self):
        return any(e["value"] == "shot" for e in self.entries)

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

    @Property(str, notify=armedChanged)
    def armed(self):
        """The add choice the next viewport click places ("mesh:box"), "" when clicking selects."""
        return self._armed

    # ---- the actions ---------------------------------------------------------------------------------------------
    @Slot(str)
    def arm(self, choice):
        """Wait for a click in the viewport to place `choice` there (the Shapes flyout's pick)."""
        if choice not in [e["value"] for e in self.entries]:
            return self.b.fail_line(f"Error: add: {choice!r} can't be added right now.")
        self._set_armed(choice)
        word = choice.partition(":")[2] or choice
        self.b.say(f"Click where the {OUTLINE_NAMES.get(word, word).lower()} goes  ·  Esc cancels")

    @Slot(str, "QVariantMap")
    def armWith(self, choice, extra):
        """Arm an outline with its source: {"svgFile": path} for a logo, {"doc2d", "layer"} for a 2D drawing."""
        self.arm(choice)
        self._extra = dict(extra or {})

    @Slot(result="QVariantList")
    def drawings(self):
        """The project's 2D items with drawn path layers (From a 2D drawing's two-level list; outline_svg.drawings)."""
        from rostrum3d.outline_svg import drawings
        try:
            return drawings(self.b.doc.folder)
        except ValueError as e:
            self.b.fail_line(f"Error: 2D drawings: {e}")
            return []

    @Slot()
    def disarm(self):
        if self._armed:
            self._set_armed("")
            self.b.say("")

    def place_at(self, hit: dict, on: tuple | None):
        """Place the armed shape: `hit` = {point, normal} in world space (placing.ground_hit or the engine's pick),
        `on` = (world transform, compiled props) of the item clicked, None for the ground. One undo step; selected."""
        choice, shape, extra = self._armed, self._armed.partition(":")[2], self._extra
        self.disarm()
        size = placing.size_class(*on) if on else placing.PRODUCT
        if shape not in OUTLINE_SHAPES:
            return self.add(choice, placing.placed(shape, hit["point"], hit["normal"], size))
        f = {**extra, **placing.outline_fields(shape, size)}
        if (below := self._below(shape, f)) is None:
            return
        made = self.add(choice, {**f, **placing.outline_placed(hit["point"], hit["normal"], hit["eye"], below, f["depth"])})
        if made and shape == "text":
            self._typer.start(made, hit.get("px"))

    def _below(self, shape, f) -> float | None:
        """How far the outline's lowest point is under its origin (its base), from the outline itself; None (and the
        status says why) when the source can't be read."""
        from rostrum3d import outline as O
        try:
            shapes = O.for_item({**F.defaults("mesh"), "shape": shape, **f, "id": shape}, self.b.doc.folder)
            return -min(p[1] for s in shapes for p in s["outer"])
        except (ValueError, OSError) as e:
            self.b.fail_line(f"Error: place: {e}")
            return None

    def _set_armed(self, choice):
        self._extra = {} if not choice else self._extra
        if choice != self._armed:
            self._armed = choice
            self.armedChanged.emit()

    @Slot(str)
    def add(self, choice, at: dict | None = None):
        """Add `choice` (an entries value); `at` = fields of where it goes (world space; placing.placed's)."""
        type_, _, detail = choice.partition(":")
        if choice not in [e["value"] for e in self.entries]:
            return self.b.fail_line(f"Error: add: {choice!r} can't be added right now.")
        new = ids.counted(index(self.b.doc.data, KIND.lists), type_)
        args = {"id": new, **START.get(type_, {})}
        if type_ == "mesh":
            args["shape"] = detail
            args["name"] = OUTLINE_NAMES.get(detail, detail.capitalize())
            if detail in OUTLINE_SHAPES:      # a flat outline pushed out: a slab 1 m deep would hide the word
                args.update(depth=0.02, bevel=0.001)
        elif type_ == "light":
            args["kind"] = detail
            args["name"] = LIGHT_NAMES.get(detail, detail.capitalize())
        elif type_ == "shot":
            args["camera"] = self._camera()
        if type_ in F.ITEMS and (into := self._holder(type_)):
            args["into"] = into
        if at:
            args.update(placing.into_parent(at, self._world(args.get("into", ""))))
        self._apply([{"op": f"{type_}.add", "args": args}], f"Add {F.LABELS[type_].lower()}", new)
        return new if self.b.doc.has(new) else ""

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

    def _holder(self, type_: str = "mesh") -> str:
        """The group or import a new item goes into: the selected one, or the one holding the selected item. A combine
        only takes solids (meshes): anything else goes where the combine itself sits."""
        if not self.b.selected:
            return ""
        doc, here = self.b.doc, self.b.selected
        while here != doc.data["id"]:        # the selected item, then each parent: the first that may hold this
            item = doc.item(here)
            if item["type"] in F.HOLDERS and (item["type"] != "combine" or type_ == "mesh"):
                return item["id"]
            here = doc.parent_of(here)[0]
        return ""

    def _world(self, id_: str):
        """The world transform of the holder `id_` at the playhead (aim.IDENTITY for the top level)."""
        if not id_:
            return placing.aim.IDENTITY
        from rostrum3d import through
        return through.find_item(self.b.viewport.sent()[0], id_, self.b.frame)[0]

    def _apply(self, calls, label, select):
        def go():
            self.b._done(self.b.doc.apply(calls, self.b.who, label=label), "")
            if select:
                self.b.select(select)
            if calls[0]["op"] == "light.add" and calls[0]["args"].get("kind") in H.PLACEABLE and self.b.viewport:
                self.b.viewport.place.start("place", select)       # the next click on a surface places it by highlight
        self.b._guard(go)
