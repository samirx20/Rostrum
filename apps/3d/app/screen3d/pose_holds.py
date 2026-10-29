"""Pose's holds and joints, for pose_drag.PoseDrag (3d-simplicity SPEC § 4): a click on the clay holds that spot (or
lets go of the hold on that part), a hold ring dragged moves to the spot under the release, a ring clicked lets go, and
Alt + a joint dot dragged moves the joint (pose.move_joint). Each one change, through the operations agents call. While
a ring or dot is dragged it follows the pointer on screen only; nothing changes until the drop. No Qt.
"""
from __future__ import annotations

from rostrum3d import aim, through

from . import gizmo as G, pose_link as L, pose_view as PV


class PoseHolds:
    def _toggle_hold(self):
        g, it = self._grab, self._item()
        self._end()
        if g is None or it is None:
            return
        on = self._held_near(g["bone"])
        if on is not None:                              # beside that part's hold ring: the click lets go
            return self._let_go(on)
        rest = g["rest"] or self._rest_spot(it, g["bone"], g["local"])
        self.b._guard(lambda: self.b._apply(L.hold_calls(it["id"], rest=rest), f"Hold {self._part(g['bone'])}"))

    def _held_near(self, bone):
        """The hold on `bone` whose ring is within LET_GO of the press, or None. A click further along a held part
        holds a second spot: two feet the finder left on the body (no foot joints) are both held; letting go on any
        click on the part released the first foot when the second was clicked ("Holds 0", critic 3d-final at 1280)."""
        rings = [r for r in self._rings if r["bone"] == bone]
        k = PV.near(rings, *self._px(*self._start), *self.v._size, PV.LET_GO * self._k())
        return rings[k] if k >= 0 else None

    def _let_go(self, ring):
        """A hold let go ({at, bone}: a ring or pose_link.holds_of's)."""
        it = self._item()
        self._end()
        if it is not None:
            self.b._guard(lambda: self.b._apply(L.hold_calls(it["id"], rest=ring["at"], off=True),
                                                f"Let go of {self._part(ring['bone'])}"))

    def _follow(self, x, y):
        """A hold ring or a joint dot dragged: it follows the pointer (screen only until the drop)."""
        w, h = self.v._size
        px, py = self._px(x, y)
        lst, k = (self._rings, self._ring_at) if self._phase == "ring" else (self._dots, self._dot_at)
        lst[k] = {**lst[k], "p": [px / w, py / h]}
        self.drawn.emit()

    def _ring_drop(self, x, y):
        ring = self._rings[self._ring_at]
        self._phase = "ringwait"
        self._ask(x, y, "ring", ring)

    def _on_ring(self, r, scene, req, ring):
        it = self._item()
        self._end()
        if isinstance(r, str):
            return self.b.fail_line(f"Error: pose: {r}")
        if it is None or not r.get("hit") or r.get("item") != it["id"]:
            return                                      # dropped off the clay: the hold stays where it was
        world = through.find_item(scene, it["id"], req["frame"])[0]
        local = aim.point(aim.invert(world), r["point"])
        on = L.bone_at(it, local, self.b.time, L.layering(self.b)[1])
        rest = r.get("rest") or self._rest_spot(it, on, local)
        calls = L.hold_calls(it["id"], rest=ring["at"], off=True) + L.hold_calls(it["id"], rest=rest)
        self.b._guard(lambda: self.b._apply(calls, f"Move hold on {self._part(on)}"))

    def _joint_drop(self, x, y):
        it, d = self._item(), self._dots[self._dot_at]
        sc, cam = self.v.sent()
        w, h = self.v._size
        view = G.View.of(cam, sc, self.b.frame, w, h)
        chain = PV.chain_of(it)
        i = next(k for k, (b, _) in enumerate(chain) if b["id"] == d["id"])
        world = through.find_item(sc, it["id"], self.b.frame)[0]
        head = aim.point(world, PV.transforms(chain, self.b.time)[i][1])
        to = G._on_plane(view, *self._px(x, y), head)
        self._end()
        self.b._guard(lambda: self.b._apply(L.move_joint_calls(it["id"], d["id"], to), f"Move joint {d['joint']}"))

    def _rest_spot(self, it, bone, local):
        """A drawn spot on the clay back on its rest shape (the engine's own `rest`, when its pick gives one, wins)."""
        chain = PV.chain_of(it)
        return PV.to_rest(chain, PV.transforms(chain, self.b.time), PV.transforms(chain, None), bone, local)

