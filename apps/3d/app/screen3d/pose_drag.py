"""Pose's pointer on the viewport, for pose_qt.Pose (3d-simplicity SPEC § 4; CANVAS § 3). Positions come in logical
px with the screen's device pixel ratio; the press always goes here and the engine's pick decides what it was:

- On the clay, a drag poses it: a move only hands its spot to the solver (pose_solver.py, its own thread: the newest
  spot waiting wins), which solves the turns from the press-time clay (pose_link.solve, so the release keys exactly
  what the last result showed); each result is drawn with the light `clay_pose` request (newest only; a view that
  refuses it previews each result in the document instead, as a bone ring drag does) and the overlay's bones. The release is ONE change: the
  Turn of every bone that moved keyed at the playhead. Esc mid-drag puts everything back with nothing in history.
- On the clay, a click (no move) holds that spot, or lets go of the hold already on that part.
- A hold ring: dragged, it moves to the spot under the release (one change); clicked, it is let go.
- Alt + a joint dot: dragged, the joint moves there (pose.move_joint, one change).
- Off the clay a left drag turns the view; a right drag turns it anywhere, a right click opens the menu.
"""
from __future__ import annotations

import copy
import sys
import time

from PySide6.QtCore import Slot
from rostrum_gui.edits import Drag
from rostrum3d import aim, through

from . import gizmo as G, pose_link as L, pose_view as PV
from .pose_holds import PoseHolds

MOVED = 3                    # logical px before a press counts as a drag
_REFUSED = [False]           # the view refused clay_pose once (an older build): every pose drag previews


class PoseDrag(PoseHolds):
    def _drag_reset(self):
        self._phase, self._up, self._moved, self._btn = "", True, False, "left"
        self._gesture = self._clay0 = self._grab = None
        self._turns, self._calls, self._live, self._busy, self._next, self._sent = {}, [], False, False, None, 0
        self._ring_at = self._dot_at = None
        self._seq, self._done_seq, self._gen, self._t_send = 0, 0, 0, 0.0

    # --- from QML
    @Slot(float, float, float, str, bool)
    def press(self, x, y, dpr, button="left", alt=False):
        if not self._on or self.v._size is None or self._phase:
            return
        self._dpr, self._start, self._last, self._up, self._moved, self._btn = dpr, (x, y), (x, y), False, False, button
        px, py = self._px(x, y)
        if button == "right":
            self._phase = "right"
        elif (k := PV.near(self._rings, px, py, *self.v._size, PV.RING_HIT * self._k())) >= 0:
            self._phase, self._ring_at = "ring", k
        elif alt and (k := PV.near(self._dots, px, py, *self.v._size, PV.DOT_HIT * self._k())) >= 0:
            self._phase, self._dot_at = "joint", k
        else:
            self._phase = "wait"
            self._ask(x, y, "press")
        self._pointer()

    @Slot(float, float)
    def move(self, x, y):
        if self._up or not self._phase:
            return
        dx, dy, self._last = x - self._last[0], y - self._last[1], (x, y)
        if not self._moved and abs(x - self._start[0]) + abs(y - self._start[1]) <= MOVED:
            return
        first, self._moved = not self._moved, True
        if self._phase == "right" or self._phase == "orbit":
            self._phase = "orbit"
            self._pointer()
            return self.v.orbit(x - self._start[0], y - self._start[1]) if first else self.v.orbit(dx, dy)
        if self._phase in ("ring", "joint"):
            return self._follow(x, y)
        if self._phase == "grab":
            self._open()
        if self._phase == "pose":
            self._aim(x, y)

    @Slot(float, float)
    def release(self, x, y):
        if self._up:
            return
        self._up, phase = True, self._phase
        if phase == "wait":
            return                                      # the pick's answer decides (_on_press)
        if phase == "right" and not self._moved:
            self._end()
            return self.menuAt.emit(x, y)
        if phase == "grab":
            return self._toggle_hold()
        if phase == "pose":                             # once the last spot's result is in (_on_solved)
            return self._commit() if self._done_seq == self._seq else None
        if phase == "ring":
            return self._ring_drop(x, y) if self._moved else self._let_go(self._rings[self._ring_at])
        if phase == "joint" and self._moved:
            return self._joint_drop(x, y)
        self._end()

    @Slot(result=bool)
    def cancel(self) -> bool:
        """Esc mid-drag: everything back as before the press, nothing in history, the hover pointer back."""
        if not self._phase:
            return False
        g, live, self._gesture = self._gesture, self._live and self._sent, None
        self.solver.stop()                              # its results still on the way are stale now
        if g is not None:
            self.b._guard(lambda: g.end(cancel=True))
        if live:                                        # the live stage shows the drag: the document's scene again
            self.v.link._forget_scene()
            self.v.redraw()
        self._end()
        return True

    # --- the press's pick
    def _on_press(self, r, scene, req):
        if self._phase != "wait":
            return
        it = self._item()
        if isinstance(r, str) or it is None or not r.get("hit") or r.get("item") != it["id"]:
            if isinstance(r, str):
                self.b.fail_line(f"Error: pose: {r}")
            if self._up and not self._moved and not isinstance(r, str):
                self._end()
                return self.v._on_picked(r.get("item", "") if r.get("hit") else "")    # a click off the clay selects
            self._phase = "orbit"                       # off the clay: the drag turns the view
            if self._moved:
                self.v.orbit(self._last[0] - self._start[0], self._last[1] - self._start[1])
            return self._end() if self._up else self._pointer()
        world = through.find_item(scene, it["id"], req["frame"])[0]
        local = aim.point(aim.invert(world), r["point"])
        bone = L.bone_at(it, local, self.b.time, L.layering(self.b)[1])
        if not bone:
            return self._end()
        self._phase = "grab"
        self._grab = {"bone": bone, "local": local, "point": r["point"], "world": world, "scene": scene, "req": req,
                      "rest": r.get("rest")}
        if self._up and not self._moved:
            return self._toggle_hold()
        if self._moved:                                 # moved before the pick answered: the drag catches up
            self._open()
            if self._phase == "pose":                  # (let go already: the result commits: _on_solved)
                self._aim(*self._last)

    # --- a pose drag
    def _open(self):
        it = self._item()

        def go():
            self._gesture = Drag(self.b.doc, self.b.who, f"Pose {self.b.label_of(it)}")
        if it is None or not self.b._guard(go):
            return self._end()
        self._clay0 = copy.deepcopy(it)
        self._held = L.held(it)
        self._live = self.v.link is not None and not _REFUSED[0]
        self._phase = "pose"
        g, req = self._grab, self._grab["req"]
        layer, stack = L.layering(self.b)               # solved as shown; the release keys the chosen layer
        self._gen = self.solver.start({
            "clay": self._clay0, "bone": g["bone"], "local": g["local"], "point": g["point"], "world": g["world"],
            "view": G.View.of(req, g["scene"], req["frame"], req["width"], req["height"]), "held": self._held,
            "holds": L.holds_of(self._clay0), "t": self.b.time, "w": req["width"], "h": req["height"], "live": self._live,
            "layer": layer, "stack": stack})
        self.timings = []

    def _aim(self, x, y):
        """A move: its spot to the solver (nothing else on the screen's thread)."""
        self._seq += 1
        self.solver.aim(*self._px(x, y), self._seq)

    def _on_solved(self, out):
        """A solver result, on the screen's thread: the clay drawn so (live, else a document preview), the overlay and
        the chip; the drop once the last spot's result is in."""
        if out["gen"] != self._gen or self._phase != "pose":
            return                                      # a drag that ended, or Esc
        t0 = time.perf_counter()
        self._done_seq = max(self._done_seq, out["seq"])
        if "error" in out:
            self.b.fail_line(f"Error: pose: {out['error']}")
        else:
            self._turns, self._calls, self._chip = out["turns"], out["calls"], out["chip"]
            if self._live:
                self.b._guard(lambda: self._send(out["pose"]))
            else:
                self.b._guard(lambda: self._gesture.preview(self._calls, fresh=True))
            d = out["drawn"]
            self._lines, self._dots, self._rings = d["lines"], d["dots"], d["rings"]
            self.drawn.emit()
            self.timings.append({**{k + "Ms": round(v, 2) for k, v in out["ms"].items()},
                                 "applyMs": round((time.perf_counter() - t0) * 1000, 2)})
        if self._up and self._done_seq == self._seq:
            self._commit()

    def _send(self, pose):
        if self._busy:
            self._next = pose
            return
        self._busy, self._sent, self._t_send = True, self._sent + 1, time.perf_counter()
        L.send_pose(self.v.link, self._clay0["id"], pose, self._answered)

    def _answered(self, out):
        self._busy = False
        if self.timings and "roundMs" not in self.timings[-1]:  # the clay_pose round trip (the view re-posed and said so)
            self.timings[-1]["roundMs"] = round((time.perf_counter() - self._t_send) * 1000, 2)
        if isinstance(out, str):                        # refused: this drag (and, on an older build, every one) previews
            self._next = None
            print(f"rostrum3d: this pose drag previews in the document instead: {out}", file=sys.stderr)
            _REFUSED[0] = _REFUSED[0] or 'no request "clay_pose"' in out
            if self._gesture is not None and self._live:
                self._live = False
                self.b._guard(lambda: self._gesture.preview(self._calls, fresh=True))
            return
        if self._next is not None and self._phase == "pose":
            nxt, self._next = self._next, None
            self._send(nxt)

    def _commit(self):
        g, calls, self._gesture, self._next = self._gesture, self._calls, None, None
        self.solver.stop()
        if g is not None:
            if not self.b._guard(lambda: self.b._done(g.end(calls=calls or None), "")) and self._live and self._sent:
                self.v.link._forget_scene()             # refused: the view shows the document again
                self.v.redraw()
        self._end(chip=True)

    # --- inside
    def _end(self, chip=False):
        self._drag_reset()
        self._chip_timer.start() if chip and self._chip else self._chip_gone()
        self._pointer()
        self._refresh()

    def _px(self, x, y):
        """Logical px to picture px."""
        k = self._dpr * self.v._scale
        return x * k, y * k

    def _k(self):
        return self._dpr * self.v._scale

    def _part(self, bone):
        it = self._item() or {}
        b = next((b for b, _ in PV.chain_of(it) if b["id"] == bone), None)
        return PV.name_of(b) if b else bone
