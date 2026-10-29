"""A material as blocks (brief 23b), for QML as `backend.blocks`: what the kit's block view (RostrumKit/BlockView.qml,
K5) draws for one material, and its signals turned into operations through the bridge, one undo step each (graph.add /
connect / set / remove; the document's side is rostrum3d/graph.py). The material's last settings row "Edit as blocks"
opens it in the bottom panel (BlocksPanel.qml); ‹ Back or Esc (esc3d.py) closes it, and so does picking an item with
another material, or another material (its own settings show; nothing picked, or an item without one, keeps them).

The picked block's settings show in the right panel (BlockSettings.qml, the kit's InspectorRow with this object as its
`bridge`): Surface = the material's own rows (as materials.py builds them); any other block = the kit's rows built from
its type's input Params (graph_blocks.py). Surface's and the stylized blocks' settings ARE the material's fields, so
they change as the material's (material.set) and a drag of a number or a colour is drawn live in the window's view and
written once at the release (material_live.py); a pattern block's own setting (Noise's Scale) is written once at the
release (graph.set: the live path knows only material fields). A setting a wire feeds says so under its field.

The view is told the blocks again only when the material's graph changed (its blocks, wires, Surface's place and the
linked inputs): a drag in the view is drawn by the view itself and lands here once, at the release.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

from PySide6.QtCore import Property, QObject, Signal, Slot
from rostrum3d import fields as F
from rostrum3d import graph as G
from rostrum3d import graph_blocks as GB
from rostrum_gui import rows, sections
from rostrum_gui import blocks as KB
from rostrum_gui.blocks import KIND_COLOURS
from rostrum_gui.edits import Scrub
from rostrum_gui.model import RowsModel

from . import material_live, outline, route

SURFACE = G.SURFACE
GAP = 60                                        # canvas units between a new block and the leftmost one
CONVERTS = {}                                   # the view's `converts`: {output kind: [input kinds it also feeds]}
for _a, _b in G.CAST:
    CONVERTS.setdefault(_a, []).append(_b)


def stops_to_paint(stops) -> dict:
    """A ramp's stops [[pos, "#hex"], …] as the kit's fill (PaintField: a linear gradient)."""
    return {"type": "linear", "stops": [{"at": float(p), "color": c, "opacity": 1} for p, c in (stops or [])]}


def paint_to_stops(paint) -> list:
    return [[round(float(s.get("at", 0)), 4), s.get("color", "#000000")] for s in (paint or {}).get("stops", [])]


def points_to_text(points) -> str:
    """A curve's points [[x, y], …] as the kit's CurveField text "x,y x,y"."""
    return " ".join(f"{x:g},{y:g}" for x, y in (points or []))


def text_to_points(text: str) -> list:
    return [[float(a), float(b)] for a, b in (p.split(",") for p in str(text).split())]


def block_rows(kind: GB.Block, vals: dict, facts: dict, linked: set) -> list[dict]:
    """A block's settings as the kit's rows (rostrum_gui.rows from its inputs' Params, as a field op's): its chain
    input (Style: only by a wire) left out; a ramp's stops as a gradient fill, a curve's points as a curve field; a
    setting a wire feeds says so under its field."""
    params = [i.param for i in kind.inputs if i.name != "style"]
    out = rows.evaluate(rows.layout(SimpleNamespace(params=params), kind.label), {**vals}, facts, False)
    for r in out:
        if r.get("row") != "param":
            continue
        if r.get("control") == "stops":
            r.update(type="paint", control="", value=stops_to_paint(r.get("value")),
                     options={"types": ["linear"], "maxStops": 8, "stopOpacity": False})
        elif r.get("control") == "points":
            r.update(type="text", control="curve", value=points_to_text(r.get("value")))
        if r["id"] in linked:
            r["note"] = {"text": "Set by a wire", "kind": "hint"}
    return out


class Blocks3D(QObject):
    changed = Signal()           # the material shown, open or not, its blocks and wires
    pickedChanged = Signal()     # the picked block and its rows
    targetChanged = Signal()     # what "Edit as blocks" would open
    rowsChanged = Signal()

    def __init__(self, bridge, parent=None):
        super().__init__(parent or bridge)
        self.b = bridge
        self._mat, self._picked, self._target = "", "", ""
        self._seen = None                       # the graph as last told to the view (compared, so no needless reset)
        self._blocks, self._wires, self._values = [], [], {}     # as the view reads them; each block's values
        self._cat = None
        self._open_groups, self._scrub, self._live, self._held = {}, None, None, None
        self.model = RowsModel(rows.ROLES, self)
        bridge.outlineChanged.connect(self._refresh)
        bridge.frameChanged.connect(self._on_frame)

    # ---- what QML reads ----------------------------------------------------------------------------------------
    @Property(bool, notify=changed)
    def open(self):
        return self._mat != ""

    @Property(str, notify=changed)
    def material(self):
        return self._mat

    @Property(str, notify=changed)
    def title(self):
        return outline.label_of(self.b.doc.item(self._mat)) if self._mat else ""

    @Property(str, notify=targetChanged)
    def target(self):
        return self._target

    @Property("QVariantList", constant=True)
    def catalogue(self):
        if self._cat is None:
            self._cat = GB.catalogue()
        return self._cat

    @Property("QVariantMap", constant=True)
    def kindColours(self):
        return dict(KIND_COLOURS)

    @Property(int, constant=True)
    def blockWidth(self):
        return KB.WIDTH

    @Property("QVariantMap", constant=True)
    def converts(self):
        return dict(CONVERTS)

    @Property("QVariantList", notify=changed)
    def blocks(self):
        return self._blocks

    @Property("QVariantList", notify=changed)
    def wires(self):
        return self._wires

    @Property(str, notify=pickedChanged)
    def selected(self):
        return self._picked

    @Property(str, notify=pickedChanged)
    def pickedLabel(self):
        if not self._picked:
            return ""
        b = next((x for x in self._blocks if x["id"] == self._picked), None)
        return b.get("label", self._picked) if b else ""

    rows = Property(QObject, lambda self: self.model, constant=True)

    @Property("QVariantList", notify=changed)
    def showMenu(self):
        """The picked block's settings that can be shown on the material (PR5), each ✓ while it is: [] for Surface
        and stylized blocks (theirs are the material's own rows already), so the button is absent there."""
        mat, kind = self._material(), self._kind(self._picked) if self._picked else None
        if mat is None or kind is None:
            return []
        shown = set((self._block(self._picked) or {}).get("shown") or ())
        return [{"value": n, "label": kind.input(n).param.label, "checked": n in shown} for n in G.showable(kind)]

    @Slot(str)
    def toggleShown(self, name):
        """Show the setting on the material, or take it away (graph.set show / hide, one undo step)."""
        if not self._mat or not self._picked:
            return
        on = name in set((self._block(self._picked) or {}).get("shown") or ())
        self._run([self._call("graph.set", {"block": self._picked, ("hide" if on else "show"): [name]})],
                  "Hide from material" if on else "Show on material")

    # ---- opening and closing ------------------------------------------------------------------------------------
    @Slot(str)
    def edit(self, material_id):
        """Edit as blocks: the bottom panel shows this material's blocks, Surface picked."""
        if not material_id or not self.b.doc.has(material_id) or self.b.doc.item(material_id).get("type") != "material":
            return self.b.fail_line(f"Error: blocks: {material_id or 'nothing'} is not a material.")
        self.endScrub()
        self._mat, self._seen, self._picked = material_id, None, SURFACE
        self._refresh()
        self.pickedChanged.emit()

    @Slot()
    def close(self):
        if not self._mat:
            return
        self.endScrub()
        self._mat, self._picked, self._seen, self._blocks, self._wires = "", "", None, [], []
        self.model.reset([])
        self.changed.emit()
        self.pickedChanged.emit()
        self.rowsChanged.emit()

    # ---- the view's signals: each one operation -------------------------------------------------------------------
    def _run(self, calls, label: str) -> bool:
        return self.b._guard(lambda: self.b._apply(calls, label))

    def _call(self, op: str, args: dict) -> dict:
        return {"op": op, "target": self._mat, "args": args}

    def _kind(self, block_id: str) -> GB.Block | None:
        """The block type of a block shown now (Surface's own for "surface")."""
        blk = self._block(block_id)
        return GB.get(blk["type"]) if blk else None

    def _material_fields(self) -> bool:
        """The picked block's settings are the material's own fields (Surface, Lines, Light to colour, Halftone):
        changed as the material's, so a drag can be drawn live (material_live.py)."""
        blk = self._block(self._picked)
        return blk is not None and (blk["type"] == SURFACE or blk["type"] in GB.STYLIZED)

    def _block(self, block_id: str) -> dict | None:
        return next((x for x in self._blocks if x["id"] == block_id), None)

    def _port_label(self, port: str) -> str:
        bid, _, name = port.partition(".")
        blk = self._block(bid) or {}
        ports = (blk.get("inputs") or []) + (blk.get("outputs") or [])
        p = next((q for q in ports if q.get("name") == name), {})
        return f"{blk.get('label', bid)} {p.get('label', name)}".strip()

    def _new_id(self, type_: str) -> str:
        have = {x["id"] for x in self._blocks}
        n = 1
        while f"{type_}_{n}" in have:
            n += 1
        return f"{type_}_{n}"

    @Slot(str, float, float, str, bool)
    def add(self, type_, x, y, from_port, placed):
        """A block from the add list at (x, y); opened from a dropped wire (`from_port` "id.output"): the new block's
        first input that output may feed is wired to it, in the same undo step. `placed` False (+ Add block, Tab: no
        point was chosen): it goes left of the leftmost block, level with Surface (wires run left to right), so it
        never lands on another block."""
        if not self._mat:
            return
        kind = GB.get(type_)
        if kind is None:
            return self.b.fail_line(f"Error: blocks: there is no block type {type_!r}.")
        if not placed and not from_port and self._blocks:
            surf = self._block(SURFACE) or self._blocks[0]
            x, y = min(b["x"] for b in self._blocks) - KB.WIDTH - GAP, surf["y"]
        bid = self._new_id(type_)
        calls = [self._call("graph.add", {"type": type_, "id": bid, "x": round(x), "y": round(y)})]
        if from_port:
            out_kind = self._out_kind(from_port)
            inp = next((i for i in kind.inputs if i.kind and G.fits(out_kind, i.kind)), None)
            if inp is not None:
                calls.append(self._call("graph.connect", {"from": from_port, "to": f"{bid}.{inp.name}"}))
        if self._run(calls, f"Add {kind.label} block"):
            self.pick(bid)

    def _out_kind(self, port: str) -> str:
        bid, _, name = port.partition(".")
        blk = self._block(bid) or {}
        return next((o.get("kind", "") for o in blk.get("outputs", []) if o.get("name") == name), "")

    @Slot(str, float, float)
    def move(self, block_id, x, y):
        self._run([self._call("graph.set", {"block": block_id, "x": round(x), "y": round(y)})], "Move block")

    @Slot(str, str)
    def wire(self, from_port, to_port):
        self._run([self._call("graph.connect", {"from": from_port, "to": to_port})],
                  f"Wire {self._port_label(from_port)} to {self._port_label(to_port)}")

    @Slot(str)
    def unwire(self, to_port):
        self._run([self._call("graph.remove", {"wires": [to_port]})], f"Remove the wire into {self._port_label(to_port)}")

    @Slot("QVariantList")
    def remove(self, ids):
        ids = [i for i in ids if i != SURFACE]
        if not ids:
            return
        word = self._block(ids[0]).get("label", ids[0]) + " block" if len(ids) == 1 and self._block(ids[0]) else f"{len(ids)} blocks"
        if self._run([self._call("graph.remove", {"blocks": list(ids)})], f"Remove {word}") and self._picked in ids:
            self.pick(SURFACE)

    @Slot(str, result="QVariantMap")
    def box(self, block_id):
        """The canvas box {x0, y0, x1, y1} of one block ("" = all of them), for the view's first placing (BlocksPanel)."""
        shown = [b for b in self._blocks if not block_id or b["id"] == block_id]
        if not shown:
            return {}
        return {"x0": min(b["x"] for b in shown), "y0": min(b["y"] for b in shown),
                "x1": max(b["x"] + KB.WIDTH for b in shown), "y1": max(b["y"] + KB.height(b) for b in shown)}

    @Slot(str)
    def pick(self, block_id):
        if block_id == self._picked:
            return
        self.endScrub()
        self._picked = block_id or ""
        self._open_groups = {}
        self._rows(new=True)
        self.pickedChanged.emit()

    # ---- inside: what the view and the rows show -----------------------------------------------------------------
    def _material(self) -> dict | None:
        return self.b.doc.item(self._mat) if self._mat and self.b.doc.has(self._mat) else None

    def _holder_target(self) -> str:
        sel = self.b.selection
        if len(sel) != 1 or not self.b.doc.has(sel[0]):
            return ""
        it = self.b.doc.item(sel[0])
        if it.get("type") == "material":
            return it["id"]
        mid = it.get("material", "")
        return mid if mid and self.b.doc.has(mid) else ""

    def _refresh(self):
        t = self._holder_target()
        if t != self._target:
            self._target = t
            self.targetChanged.emit()
            if self._mat and t and t != self._mat:      # another item (or material) picked: its own settings, the timeline
                return self.close()
        if not self._mat:
            return
        mat = self._material()
        if mat is None or mat.get("type") != "material":          # undone, removed: nothing to show
            return self.close()
        first = self._seen is None
        d = G.describe(mat, catalogue=False)
        seen = json.dumps(d, sort_keys=True, default=str)
        if seen != self._seen:
            self._seen = seen
            self._values = {blk["id"]: blk.get("values") or {} for blk in d["blocks"]}
            self._blocks = [{k: v for k, v in blk.items() if k not in ("values", "on")} for blk in d["blocks"]]
            self._wires = d["wires"]
            self.changed.emit()
            if self._picked and self._block(self._picked) is None:
                self._picked = SURFACE
                self.pickedChanged.emit()
        self._rows(new=first)

    def _on_frame(self):
        mat = self._material()
        if self._picked == SURFACE and mat is not None and mat.get("keys"):
            self._rows()

    def _linked(self) -> set[str]:
        """The picked block's inputs a wire feeds."""
        return {w["to"].partition(".")[2] for w in self._wires if w["to"].partition(".")[0] == self._picked}

    def _rows(self, new: bool = False):
        mat = self._material()
        if mat is None or not self._picked:
            self.model.reset([])
        elif self._picked == SURFACE:
            op = self.b.doc.kind.registry.field_op("material")
            out = rows.evaluate(sections.layout(op, "material"), route.shown_values(mat, self.b.time),
                                self.b.facts_of(mat), False, opened=self._open_groups)
            linked = self._linked()
            for r in out:
                if r.get("row") == "param" and r["id"] in linked:
                    r["note"] = {"text": "Set by a wire", "kind": "hint"}
            self.model.reset(out) if new else self.model.update(out)
        else:
            kind = self._kind(self._picked)
            facts = self.b.facts_of(mat) if self._material_fields() else {}
            out = block_rows(kind, self._values.get(self._picked, {}), facts, self._linked()) if kind else []
            self.model.reset(out) if new else self.model.update(out)
        self.rowsChanged.emit()

    # ---- the rows: InspectorRow's bridge -------------------------------------------------------------------------
    def _block_value(self, param, value):
        """A block row's value as the document keeps it (a ramp's stops, a curve's points)."""
        kind = self._kind(self._picked)
        inp = kind.input(param) if kind else None
        control = inp.param.control if inp else ""
        if control == "stops" and isinstance(value, dict):
            return paint_to_stops(value)
        if control == "points" and isinstance(value, str):
            return text_to_points(value)
        return value

    def _set_block(self, param, value) -> bool:
        kind = self._kind(self._picked)
        inp = kind.input(param) if kind else None
        label = f"{kind.label}: {inp.param.label}" if inp else f"Change {param}"
        return self._run([self._call("graph.set", {"block": self._picked, "values": {param: self._block_value(param, value)}})],
                         label)

    @Slot(str, "QVariant", result=bool)
    def setValue(self, param, value):
        if not self._mat or not self._picked:
            return False
        if self._material_fields():
            return self._run([self.b.edit_call(self._mat, param, value)], f"Material: {param}")
        return self._set_block(param, value)

    @Slot(str)
    def beginScrub(self, param):
        self.endScrub()
        if not self._mat or not self._picked:
            return
        if not self._material_fields():              # a block's own setting: written once at the release
            self._held = [param, None]
            return
        if material_live.ok(self.b, param):        # drawn live in the window's view, written once at the release
            mat = self.b.doc.item(self._mat)
            self._live = material_live.Drag(self.b, self._mat, param, mat.get(param, F.param("material", param).default),
                                            lambda _why: self._live_refused())
            return
        self.b._guard(lambda: setattr(self, "_scrub", Scrub(self.b.doc, self.b.who, [self._mat], param, self.b.edit_call)))

    @Slot(str, "QVariant")
    def scrub(self, param, value):
        if self._held is not None and self._held[0] == param:
            self._held[1] = value
            return
        if self._live is not None and self._live.param == param:
            return self._live.send(value)
        if self._scrub is None or self._scrub.name != param:
            self.beginScrub(param)
            if self._held is not None:
                self._held[1] = value
                return
            if self._live is not None:
                return self._live.send(value)
        if self._scrub is not None:
            self.b._guard(lambda: self._scrub.preview(value))

    def _live_refused(self):
        lv, self._live = self._live, None
        if lv is not None and self._mat:
            self.b._guard(lambda: setattr(self, "_scrub", Scrub(self.b.doc, self.b.who, [self._mat], lv.param,
                                                                 self.b.edit_call)))
            if lv.value is not None and self._scrub is not None:
                self.b._guard(lambda: self._scrub.preview(lv.value))

    def _end(self, cancel: bool):
        held, self._held = self._held, None
        if held is not None:
            if not cancel and held[1] is not None:
                self._set_block(*held)
            return
        if self._live is not None:
            lv, self._live = self._live, None
            value = lv.end(cancel)
            if value is not None:
                self._run([self.b.edit_call(lv.material, lv.param, value)], f"Material: {lv.param}")
            return
        s, self._scrub = self._scrub, None
        if s is not None:
            self.b._guard(lambda: self.b._done(s.end(cancel), ""))

    @Slot()
    def endScrub(self):
        self._end(cancel=False)

    @Slot()
    def cancelScrub(self):
        self._end(cancel=True)

    @Slot(str)
    def toggleGroup(self, group):
        if self._picked != SURFACE:
            return
        row = next((r for r in self.model.rows if r.get("fold") == group), None)
        if row and row.get("own"):
            return
        if row and row.get("switch"):           # Lines, Halftone …: its name adds it, its − removes it
            self.setValue(row["switch"], row["off"] if row["open"] else row["on"])
            return
        self._open_groups[group] = not (row and row["open"])
        self._rows()

    @Slot(str)
    def toggleAnimate(self, param):
        self.b.fail_line("Error: material settings are not keyed from the blocks: select the material (Edit) to key them.")
