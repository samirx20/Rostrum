"""One drag step of the gizmo on a whole item (SPEC 4.1), the maths behind gizmo_qt.py's dragTo: the item's own fields
(x y z, rx ry rz, sx sy sz, px py pz) a move, turn or scale puts it at, and the readout. No Qt. Edit mesh's drags are
mesh_gizmo.py's.
"""
from __future__ import annotations

from rostrum_gui.snap import Target
from rostrum3d import aim

from . import gizmo as G

MOVE, TURN, SCALE, PIVOT = ("x", "y", "z"), ("rx", "ry", "rz"), ("sx", "sy", "sz"), ("px", "py", "pz")


def _arm_px(g):
    (ax, ay), (bx, by) = g["line"]
    return max(1.0, ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5 / g["ctx"]["px"])


def item_drag(g, c, now, free, targets):
    """({field: value}, readout) for the grab `g` (its context `c`) with the pointer at `now`; `targets(c, field)` lists
    what a move along that axis catches."""
    v, label = c["v"], ""
    units = c["view"].units(c["view"].project(c["origin"])[2]) * c["px"]     # world units per screen px
    if g["kind"] in ("move", "pivot"):
        d = aim._apply(aim._inverse(c["pw"][0]), G.moved_by(c["view"], g["handle"], c["origin"], c["axes"], g["start"], now))
        out = {k: v[k] + d[i] for i, k in enumerate(MOVE)}
        if g["handle"] != "plane":
            k = MOVE[int(g["handle"][-1])]
            out[k], caught = G.snapped(out[k], targets(c, k), 1 / units, free)
            label = f"{k.upper()} {out[k]:.3f} m" + (f" · {caught}" if caught else "")
        if g["kind"] == "pivot":
            lin = aim._inverse(aim.local({**v, "x": 0.0, "y": 0.0, "z": 0.0})[0])
            dp = aim._apply(lin, [out[k] - v[k] for k in MOVE])
            out.update({k: v[k] + dp[i] for i, k in enumerate(PIVOT)})
    elif g["kind"] == "turn":
        deg = G.turned_by(c["view"], g["handle"], c["origin"], c["axes"], g["start"], now)
        deg, caught = G.snapped(deg, G.angle_targets(deg), G.ARM * 0.8 * 3.14159 / 180, free)
        m = aim._mul(G.turn_matrix(G.AXES[int(g["handle"][-1])], deg), c["turn"])   # around the parent's axis
        out = dict(zip(TURN, aim._euler(m)))
        label = f"Turn {deg:.1f}°"
    else:
        f = G.scaled_by(g["line"], g["start"], now)
        f, caught = G.snapped(f, [Target("measure", "×1", 1.0), Target("measure", "×2", 2.0),
                                  Target("measure", "×½", 0.5)], _arm_px(g), free)
        k = SCALE[int(g["handle"][-1])]
        out = {k: max(0.0, v[k] * f)}
        label = f"Scale ×{f:.2f}"
    return out, label
