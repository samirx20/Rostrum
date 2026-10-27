"""The gizmo on screen, for QML as `gizmo` (SPEC §4.1, §14): the selected item's move / turn / scale handles (V all,
W move, E turn, S scale; D held moves the pivot instead), each drag one doc.gesture = one undo step, written through
the bridge's own edit_call (an animated field gets its key at the playhead). While the pointer moves, the window's own
view moves the item by itself and the document changes once, at the drop (gizmo_live.py; where it can't, each move is
previewed in the document as before and the settings panel follows live). Esc cancels a drag mid-way (esc3d.py). K keys
what the gizmo moved on the item at the playhead. Agents do the same with the same operations (`value.set`,
`key.add` on x y z, rx ry rz, sx sy sz, px py pz). A selected bone whose chain is drawn (Animate) gets turn rings on its
head, each drag keying its Turn at the playhead (gizmo_bone.py). The maths is gizmo.py's.
"""
from __future__ import annotations

from PySide6.QtCore import Property, QObject, Signal, Slot
from PySide6.QtGui import QGuiApplication
from rostrum_gui.edits import Drag
from rostrum_gui.snap import Target
from rostrum3d import aim, fields as F, resolve

from . import gizmo as G, gizmo_bone, gizmo_live as live, route
from .gizmo_drag import MOVE, TURN, SCALE, PIVOT, item_drag
from .gizmo_hold import HoldD
from .viewport import scene_ids

SHOWN = ("all", "move", "turn", "scale")


class Gizmo(live.LiveDrag, QObject):
    changed = Signal()

    def __init__(self, bridge, viewport):
        super().__init__(viewport)
        self.bridge, self.vp = bridge, viewport
        self._show, self._pivot, self._hs, self._label = "all", False, [], ""
        self._drag, self._moved = None, {}            # the open drag; item id -> fields the gizmo moved (for K)
        self._live = None                             # the open drag's live sender (gizmo_live.Sender), when live
        viewport.serialChanged.connect(self._refresh)
        bridge.selectionChanged.connect(self._refresh)
        viewport.mesh_edit.changed.connect(self._refresh)      # Edit mesh: the gizmo stands on the selection
        viewport.paint.changed.connect(self._refresh)          # Paint: no gizmo (a drag paints; it would hide the strokes)
        viewport.clay_tool.changed.connect(self._refresh)      # Clay: no gizmo either (a drag sculpts)
        bridge.pageChanged.connect(self._refresh)              # a bone's rings show where its chain is drawn (Animate)
        self._hold = HoldD(self) if isinstance(QGuiApplication.instance(), QGuiApplication) else None

    show = Property(str, lambda s: s._show, notify=changed)
    pivot = Property(bool, lambda s: s._pivot, notify=changed)
    handles = Property("QVariantList", lambda s: s._hs, notify=changed)   # in parts of the viewport (0..1)
    label = Property(str, lambda s: s._label, notify=changed)
    dragging = Property(bool, lambda s: s._drag is not None, notify=changed)

    # --- what is selected, as the gizmo needs it
    def _item(self):
        sel = self.bridge.selected
        if not sel or not self.bridge.doc.has(sel):
            return None
        it = self.bridge.doc.item(sel)
        if it["type"] == "bone":                    # turned where its chain is drawn, not while Bones places one
            return it if self.vp.bone_tool._shown_mesh() and not self.vp.bone_tool.on else None
        if it["type"] not in F.ITEMS or "x" not in {p.name for p in F.FIELDS[it["type"]]}:
            return None
        if it["type"] == "light" and it.get("kind") == "dome":
            return None
        return it

    def _values(self, it):
        t = self.bridge.time
        v = {p.name: it.get(p.name, p.default) for p in F.FIELDS[it["type"]]}
        v.update({k: route.value_at(it, k, t) for k in MOVE + TURN + SCALE + PIVOT if k in v})
        v.setdefault("aim", "none")
        v.update({k: v.get(k, 1.0) for k in SCALE} | {k: v.get(k, 0.0) for k in PIVOT})   # a rig has neither
        return v

    def _setup(self):
        it, vp = self._item(), self.vp
        if it is None or vp._size is None or vp.paint.on or vp.clay_tool.on or getattr(vp, "pose_tool", None) and vp.pose_tool.on:
            return None
        scene, cam = vp.sent()
        w, h = vp._size
        view = G.View.of(cam, scene, self.bridge.frame, w, h)
        v = self._values(it)
        screen = QGuiApplication.primaryScreen()
        px = vp._scale * (screen.devicePixelRatio() if screen else 1.0)
        if it["type"] == "bone":        # on its head, posed at the playhead; the rings around its parent's axes
            pw, origin, turn = gizmo_bone.frame(self.bridge.doc, it, v, scene, self.bridge.frame, self.bridge.time)
            return {"it": it, "v": v, "view": view, "pw": pw, "origin": origin, "turn": turn, "axes": G.columns(pw[0]),
                    "own": G.columns(aim._mul(pw[0], turn)), "px": px, "scene": scene, "parent": None, "mesh": False}
        parent = self.bridge.doc.parent_of(it["id"])[0]
        parent = parent if parent in scene_ids(scene) else None        # a top-level item's parent is the document
        shot = self.bridge.shot_info()
        carrier = resolve.seen(self.bridge.doc.data, it["id"], self.bridge.frame, shot["fps"], shot.get("start", 0))
        pw, origin, turn = G.item_frame(carrier, v)
        axes, own = G.columns(pw[0]), G.columns(aim._mul(pw[0], turn))
        me = self.vp.mesh_edit
        if me.on:                       # Edit mesh: on the picked points / edges / faces, along the item's own axes
            spot = me.gizmo_frame()
            if spot is None:
                return None
            origin, axes, own = spot["origin"], spot["own"], spot["own"]
        return {"it": it, "v": v, "view": view, "pw": pw, "origin": origin, "turn": turn, "axes": axes, "own": own, "px": px,
                "scene": scene, "parent": parent, "mesh": me.on}

    def _refresh(self, *_):
        if self._live is not None:      # a live drag: the document stands still, the handles follow the drag (dragTo)
            return
        self._ctx = None
        try:
            self._ctx = self._setup()
        except Exception as e:  # noqa: BLE001  no gizmo when the item can't be placed; said, not hidden
            self.bridge.fail_line(f"Error: gizmo: {e}")
        self._place()

    def _place(self):
        c = getattr(self, "_ctx", None)
        show = "turn" if c and c["it"]["type"] == "bone" else "move" if self._pivot else self._show    # a bone only turns
        hs = [] if c is None else G.handles(c["view"], c["origin"], c["axes"], c["own"], show,
                                            c["v"].get("aim", "none") != "none", c["px"])
        w, h = self.vp._size or (1, 1)
        frac = lambda p: [p[0] / w, p[1] / h]          # noqa: E731
        self._raw = hs
        self._hs = [{**x, **({"points": [frac(p) for p in x["points"]]} if "points" in x else
                             {"a": frac(x["a"]), "b": frac(x["b"])})} for x in hs]
        self.changed.emit()

    # --- slots for QML (positions in parts of the viewport, 0..1)
    def _pt(self, fx, fy):
        w, h = self.vp._size
        return [fx * w, fy * h]

    @Slot(str)
    def setShow(self, show):
        if show in SHOWN and show != self._show:
            self._show = show
            self._place()

    @Slot(bool)
    def setPivot(self, on):
        if bool(on) != self._pivot:
            self._pivot = bool(on)
            self._place()

    @Slot(float, float, result=str)
    def hitAt(self, fx, fy):
        c = getattr(self, "_ctx", None)
        return "" if c is None or self.vp._size is None else G.hit(self._raw, *self._pt(fx, fy), c["px"])

    @Slot(str, float, float, result=bool)
    def begin(self, handle, fx, fy):
        c = getattr(self, "_ctx", None)
        if c is None or not handle:
            return False
        kind = next(h["kind"] for h in self._raw if h["id"] == handle)
        kind = "pivot" if self._pivot and kind == "move" else kind       # (a bone's rings stay rings with D held)
        words = {"move": "Move", "turn": "Turn", "scale": "Scale", "pivot": "Move pivot"}[kind]

        def go():
            self._drag = Drag(self.bridge.doc, self.bridge.who, f"{words} {self.bridge.label_of(c['it'])}")
        self._grab = {"handle": handle, "kind": kind, "start": self._pt(fx, fy), "ctx": c, "calls": [],
                      "line": next(((h["a"], h["b"]) for h in self._raw if h["id"] == handle and "a" in h), None)}
        if not self.bridge._guard(go):
            return False
        self._live = None if live.why_not(self.bridge, self.vp, c) else live.Sender(self.vp.link, self._unlive)
        self.changed.emit()
        return True

    @Slot(float, float, bool)
    def dragTo(self, fx, fy, free):
        if self._drag is None:
            return
        g, now = self._grab, self._pt(fx, fy)
        c, v = g["ctx"], g["ctx"]["v"]
        if c["mesh"]:
            return self._mesh_drag(g, c, now, free)
        out, self._label = item_drag(g, c, now, free, self._targets)
        has = {p.name for p in F.FIELDS[c["it"]["type"]]}
        out = {k: x for k, x in out.items() if k in has}
        calls = [self.bridge.edit_call(c["it"]["id"], k, x) for k, x in out.items() if abs(x - v[k]) > 1e-9]
        if c["it"]["type"] == "bone":   # keys on its Turn, every field moved so far in this drag (gizmo_bone.py)
            g.setdefault("moved", set()).update(k for k in out if abs(out[k] - v[k]) > 1e-9)
            calls = gizmo_bone.calls(c["it"]["id"], {k: out[k] for k in g["moved"]}, self.bridge.time)
        self._moved.setdefault(c["it"]["id"], set()).update(k for k in out if abs(out[k] - v[k]) > 1e-9)
        g["calls"] = calls
        if self._live is None:
            self.bridge._guard(lambda: self._drag.preview(calls))
        else:                           # the view moves the item; the handles move with it; the document waits
            return self._live_move(c, {**v, **out})
        self.changed.emit()

    def _mesh_drag(self, g, c, now, free):
        """Edit mesh: each move one `mesh.transform` step on top of the drag so far (mesh_gizmo.py works it out)."""
        call, self._label = self.vp.mesh_edit.gizmo_step(g, c, now, free)
        self.bridge._guard(lambda: self._drag.preview([call]))
        self.changed.emit()

    def _targets(self, c, k):
        """Where a move along one axis catches: the ground's 0 and the other items' places on that axis."""
        others = [i for i in self.bridge.doc.items() if i.get("type") in F.ITEMS and i["id"] != c["it"]["id"]
                  and "x" in {p.name for p in F.FIELDS[i["type"]]}]
        return [Target("edge", "0", 0.0)] + [Target("centre", self.bridge.label_of(i), float(i.get(k, 0.0))) for i in others]

    @Slot(float, float)
    def tap(self, fx, fy):
        """A click on a handle that never dragged: a bone drawn there is picked (bones_qt.bone_at, in device px)."""
        bone = self.vp.bone_tool.bone_at(*(p / self.vp._scale for p in self._pt(fx, fy)))
        if bone:
            self.vp._on_picked(bone)

    @Slot()
    def keyMoved(self):
        """K: a key at the playhead on each field the gizmo moved on the selected item (Position when nothing yet)."""
        it = self._item()
        if it is None:
            return self.bridge.fail_line("Nothing to key: select an item first.")
        t, fps = self.bridge.time, self.bridge.shot_info()["fps"]
        props = sorted(self._moved.get(it["id"]) or MOVE, key=(MOVE + TURN + SCALE + PIVOT).index)
        calls = []
        for p in props:
            if route.anim_state(it, p, t, fps) == "still":
                calls += route.animate_calls(it, p, t, fps)[0]
            else:
                calls.append(route.value_call(it, p, route.value_at(it, p, t), t))
        self.bridge._guard(lambda: self.bridge._apply(calls, f"Key {', '.join(props)} of {self.bridge.label_of(it)}"))
        self._moved.pop(it["id"], None)
