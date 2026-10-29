"""Rostrum3D's keys that are not actions on the selection: the one hub (`KeyHub3D`, the kit's ActionHub) answers every job
of the key map (keys3d.py). Before anything else a mode that is under way takes the key it uses (`mode_takes`: the Knife's
Enter cuts, the bones being placed take Enter and Delete); then a job in ROUTES calls a bridge method (KeyRoutes3D,
below); a job in WINDOW is the window's own (Main.qml `windowJobs`: it needs the rail); an action of the list
(actions3d.py) runs through the kit; the rest (keys3d.SKIP) are bound by the kit's AppShell and FilesMenu.
tests/test_keys_wired.py keeps the lists honest.
"""
from __future__ import annotations

from PySide6.QtCore import Property, Signal, Slot
from rostrum_gui.action_hub import ActionHub
from rostrum_gui.parts import SlotMixin
from rostrum3d import fields as F

from rostrum_core.keys.layers import stack_of
from . import esc3d, route
from .keys3d import ROUTES, SKIP, WINDOW

NUDGE_STEP = {"": 0.01, "big": 0.1, "fine": 0.001}          # metres: 1 cm, Shift 10 cm, Alt 1 mm
NUDGE_AXIS = {"left": ("x", -1), "right": ("x", 1), "up": ("y", 1), "down": ("y", -1)}


class KeyHub3D(ActionHub):
    windowJob = Signal(str)             # a job only the window can run: Main.qml answers it

    def __init__(self, bridge, *a, **kw):
        super().__init__(*a, parent=bridge, **kw)
        self.bridge = bridge

    @Property("QVariantList", constant=True)
    def skip(self):
        return SKIP

    @Slot(str)
    def key(self, job):
        if self.bridge.mode_takes(job):
            return
        if job in ROUTES:
            name, *args = ROUTES[job]
            getattr(self.bridge, name)(*args)
        elif job in WINDOW:
            self.windowJob.emit(job)
        else:
            super().key(job)

    def run_job(self, job):
        """Ctrl+K named a job of the key map (not an action): as its key would, else the window's (Main.qml, then the
        kit's AppShell.runJob)."""
        if job in ROUTES or job in WINDOW or self.list.keymap.has(job) and any(self.list.job_of(a) == job for a in self.list.actions):
            self.key(job)
        else:
            self.windowJob.emit(job)


def _vp(b):
    return getattr(b, "viewport", None)


class KeyRoutes3D(SlotMixin):
    """The bridge methods keys3d.ROUTES names (and `mode_takes`, which the hub asks first)."""

    def mode_takes(self, job) -> bool:
        """A mode under way takes the keys it uses: the Knife's line (Enter cuts), the bones being placed (Enter makes the
        chain, Delete / Backspace takes the last point back)."""
        vp = _vp(self)
        if vp is None:
            return False
        if job == "go_in" and vp.mesh_edit.knifing:
            vp.mesh_edit.knifeApply()
            return True
        if job in ("go_in", "delete") and vp.bone_tool.on:
            vp.bone_tool.make() if job == "go_in" else vp.bone_tool.back()
            return True
        if job == "delete" and getattr(vp, "pose_tool", None) is not None and vp.pose_tool.on:          # Pose: the hold under the pointer (never the clay itself)
            vp.pose_tool.delete_hovered()
            return True
        return False

    # ---- time ----------------------------------------------------------------------------------------------------
    @Slot()
    def toStart(self):
        self.setFrame(self._info["start"])

    @Slot()
    def toEnd(self):
        self.setFrame(self._info["end"])

    @Slot(int)
    def stepFrames(self, n):
        """Ctrl+Left / Right (one frame), with Shift (ten)."""
        self.setFrame(self._frame + n)

    def _event_times(self) -> list[float]:
        """The keys of the selected items (of every item when none is), and the markers: what `,` and `.` step to."""
        owners = [i for i in self.selection if self.doc.has(i) and self.doc.item(i)["type"] in F.ITEMS] or None
        items = [self.doc.item(i) for i in owners] if owners else [it for it in self.doc.items() if it.get("type") in F.ITEMS]
        return sorted({k["t"] for it in items for k in it.get("keys", [])} | {m["at"] for m in self.marks.rows()})

    @Slot(int)
    def eventJump(self, sign):
        """, and . : the playhead to the previous / next key (of the selection, else of every item) or marker."""
        fps, here, lo, hi = self._info["fps"], self._frame, self._info["start"], self._info["end"]
        frames = sorted({min(max(round(t * fps), lo), hi) for t in self._event_times()})     # a key at the shot's end: its last frame
        to = [f for f in frames if f > here] if sign > 0 else [f for f in frames if f < here]
        if not to:
            return self._set_status("No later key or marker" if sign > 0 else "No earlier key or marker")
        self.setFrame(to[0] if sign > 0 else to[-1])

    @Slot()
    def markerHere(self):
        """M: a marker at the playhead."""
        if self.marks.add(self.time):
            self._set_status(f"Marker added at {self.time:.2f} s")

    @Slot(int)
    def markerJump(self, sign):
        """Alt+M / Alt+Shift+M: the playhead to the next / previous marker (a clear word when there is none)."""
        fps = self._info["fps"]
        frames = sorted({round(m["at"] * fps) for m in self.marks.rows()})
        to = [f for f in frames if f > self._frame] if sign > 0 else [f for f in frames if f < self._frame]
        if not to:
            return self._set_status("No next marker" if sign > 0 else "No earlier marker")
        self.setFrame(to[0] if sign > 0 else to[-1])

    # ---- the selection -------------------------------------------------------------------------------------------
    def _scene_order(self) -> list[str]:
        return [r["id"] for r in self.sceneRows if r["row"] == "layer"]

    @Slot()
    def selectAllItems(self):
        """Ctrl+A: every item of the scene list as it shows (folded groups' insides stay out)."""
        order = self._scene_order()
        if order:
            self.selectMany(order)

    @Slot(int)
    def walk(self, sign):
        """Tab / Shift+Tab: the next / previous item of the scene list as it shows (one pick)."""
        order = self._scene_order()
        if not order:
            return
        here = self.selectedOwner
        i = order.index(here) + sign if here in order else (0 if sign > 0 else -1)
        self.select(order[i % len(order)])

    @Slot()
    def goIn(self):
        """Enter: on a shape or combine, Edit mesh (as 2D's Enter edits a path's points); on a group, its first item."""
        vp, sel = _vp(self), self.selected
        if not sel or not self.doc.has(sel) or (vp is not None and vp.mesh_edit.on):
            return
        it = self.doc.item(sel)
        if it["type"] in F.SOLIDS:
            return self._hub.run("mesh:edit")
        kids = it.get("children") or []
        if kids:
            self.select(kids[0]["id"])

    @Slot()
    def goOut(self):
        """Shift+Enter: out of Edit mesh; else the group the selected item is in becomes the selection."""
        vp, sel = _vp(self), self.selected
        if vp is not None and vp.mesh_edit.on:
            return vp.mesh_edit.leave()
        if sel and self.doc.has(sel):
            parent = self.doc.parent_of(sel)[0]
            if parent and parent != self.doc.data["id"] and self.doc.item(parent)["type"] in F.ITEMS:
                self.select(parent)

    @Slot(result=str)
    def stepBack(self):
        """Esc (after the kit's own Esc closed any open popup or sheet): the first step of esc3d.ORDER that applies."""
        return esc3d.step(self)

    # ---- moving and keying ----------------------------------------------------------------------------------------
    def _movable(self) -> list[dict]:
        out = []
        for i in self.selection:
            it = self.doc.item(i) if self.doc.has(i) else None
            if it and it["type"] in F.ITEMS and "x" in {p.name for p in F.FIELDS[it["type"]]} and not (
                    it["type"] == "light" and it.get("kind") == "dome"):
                out.append(it)
        return out

    @Slot(str)
    def nudgeKey(self, how):
        """An arrow key (keys3d.NUDGE: "left", "up_big" …): the selected items move along the world's X (left / right) or Y
        (up / down) by 1 cm, 10 cm with Shift, 1 mm with Alt; an animated position gets its key at the playhead. One undo
        step per press. Not in Edit mesh or Paint (the arrows have no meaning there yet)."""
        vp = _vp(self)
        if vp is not None and (vp.mesh_edit.on or vp.paint.on):
            return
        items = self._movable()
        if not items:
            return
        name, _, size = how.partition("_")
        axis, sign = NUDGE_AXIS[name]
        step = sign * NUDGE_STEP[size]
        calls = [self.edit_call(it["id"], axis, round(route.value_at(it, axis, self.time, stack_of(self.doc.data)) + step, 6)) for it in items]
        label = f"Nudge {self.selection_label([it['id'] for it in items])}"
        self._guard(lambda: self._done(self.doc.apply(calls, self.who, label=label, join=False), ""))   # never joined to the last

    @Slot()
    def keyHere(self):
        """K: a key at the playhead on what the gizmo moved (gizmo_qt.keyMoved). Not in Edit mesh (the points have no keys)."""
        vp = _vp(self)
        if vp is not None and not vp.mesh_edit.on:
            vp.gizmo.keyMoved()

    @Slot(str)
    def easeKey(self, ease):
        """F9 and its neighbours: the picked keys get that ease (one undo step); no keys picked: says so."""
        if not self._keys.count:
            return self._set_status("Pick keys on the timeline first")
        self._keys.setEase(ease)

    # ---- the view, the tools, the modes ---------------------------------------------------------------------------
    @Slot(int)
    def zoomKey(self, sign):
        vp = _vp(self)
        if vp is not None:
            vp.zoom(sign)

    @Slot()
    def selectTool(self):
        """V: Select: Paint is left, a shape waiting for its click is let go, the gizmo shows all its handles."""
        vp = _vp(self)
        self.add.disarm()
        if vp is not None:
            vp.paint.leave()
            vp.clay_tool.leave()
            vp.pose_tool.leave()
            vp.gizmo.setShow("all")

    @Slot()
    def paintKey(self):
        """B: Paint on the selected mesh or clay, in and out (paint_mode_qt.py); not with nothing paintable. (Bones is Shift+B.)"""
        vp = _vp(self)
        if vp is None:
            return
        if vp.paint.on or vp.paint.can:
            vp.clay_tool.leave()
            vp.paint.toggle()
        else:
            self._set_status("Paint needs one mesh or clay selected (Bones is Shift+B)")

    @Slot()
    def onionKey(self):
        vp = _vp(self)
        if vp is not None and self._page == "animate":
            vp.onion.toggle()

    @Slot()
    def bonesKey(self):
        """Shift+B: Bones on the selected mesh (the Animate page, where bones are drawn), or out of it when placing."""
        vp = _vp(self)
        if vp is None:
            return
        if vp.bone_tool.on:
            return vp.bone_tool.cancel()
        if self._page != "animate" and vp.bone_tool.meshSelected:
            self.setPage("animate")
        vp.bone_tool.start()

    @Slot()
    def poseKey(self):
        """Shift+P: Pose on the selected clay, in and out (pose_qt.py)."""
        vp = _vp(self)
        if vp is None:
            return
        if vp.pose_tool.on or vp.pose_tool.can:
            vp.pose_tool.toggle()
        else:
            self._set_status("Pose needs one clay selected")

    @Slot(str)
    def gizmoKey(self, show):
        vp = _vp(self)
        if vp is not None:
            vp.gizmo.setShow(show)

    @Slot(str)
    def meshKind(self, kind):
        vp = _vp(self)
        if vp is not None and vp.mesh_edit.on and not vp.mesh_edit.needsEdit:
            vp.mesh_edit.setKind(kind)

    @Slot()
    def meshXray(self):
        vp = _vp(self)
        if vp is not None and vp.mesh_edit.on and not vp.mesh_edit.needsEdit:
            vp.mesh_edit.toggleXray()

    @Slot()
    def meshKnife(self):
        vp = _vp(self)
        if vp is not None and vp.mesh_edit.on and not vp.mesh_edit.needsEdit:
            vp.mesh_edit.toggleKnife()

    @Slot()
    def shotViewKey(self):
        """`: the shot camera's view, or the free camera from it."""
        vp = _vp(self)
        if vp is not None and vp.hasShot:
            vp.setMode("free" if vp.mode == "shot" else "shot")

    @Slot()
    def lookKey(self):
        vp = _vp(self)
        if vp is not None:
            vp.toggleLook()

    @Slot()
    def renderKey(self):
        """F12: the header's Render (the Final picture of this frame, at once); on the Render page, the shown shot's
        Render (next in the queue). The render sheet is Ctrl+E or the ▾ beside Render."""
        if self._page == "render":
            self.queue.renderNext(self.shot_id)
        else:
            self.render.start()
