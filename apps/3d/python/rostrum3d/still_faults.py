"""frozen_end:<shot> (round 7 of the 3D gaps: judges marked Spill and Drape "hangs still", "frozen for half"): the shot's last
STILL_S seconds or more have no motion at all. An entry of the shot's one fault list (faults.py).

Everything that can move is compared with how it is on the shot's last frame, every STEP frames: each item's world
transform (keys, rigs, aims, follows, simulated falls as the stored result lays them), its other keyed values (a light's
intensity, a visible toggle), a posed figure's bones, a cloth's points and each falling copy. The last frame that differs
is where the motion ends; a settled simulation reads as still. Nothing is rendered.
"""
from __future__ import annotations

import math

from rostrum_core.keys import animated
from rostrum_core.mcp import faults as F

from . import skin

STILL_S = 2.0            # a still end longer than this is a frozen end
STEP = 2                 # frames: compare every this many
MOVE_M = 0.001           # a point moved less than this has not moved
TURN = 0.003             # a transform's axes changed less than this (about 0.2°) has not turned
_PLACE = {"x", "y", "z", "rx", "ry", "rz", "sx", "sy", "sz", "px", "py", "pz"}


def _differs(a, b) -> bool:
    (la, ta), (lb, tb) = a, b
    return math.dist(ta, tb) > MOVE_M or any(abs(x - y) > TURN for ra, rb in zip(la, lb) for x, y in zip(ra, rb))


def _other(v: dict, w: dict) -> bool:
    for k in v:
        x, y = v[k], w.get(k)
        if isinstance(x, bool) or not isinstance(x, (int, float)):
            if x != y:
                return True
        elif not isinstance(y, (int, float)) or abs(x - y) > 1e-4 * max(1.0, abs(x)):
            return True
    return False


def _last_change(fr, ids, frames, end) -> tuple[int, str] | None:
    """The last of `frames` (going back from the end) where anything differs from frame `end`, and what; None if nothing."""
    keyed = {i: [p for p in animated(fr.items[i]) if p not in _PLACE] for i in ids}
    bones = {i: skin.bones_of(fr.items[i]) for i in ids if fr.items[i]["type"] == "clay" and fr.items[i].get("bones")}

    def pose(i, f):
        return skin.transforms(bones[i], fr.held(i, f) / fr.fps)

    final = {i: (fr.world(i, end), {p: fr.values(i, end).get(p) for p in keyed[i]}, pose(i, end) if i in bones else None)
             for i in ids}
    for f in reversed(frames):
        for i in ids:
            m, vals, bs = final[i]
            v = fr.values(i, f)
            if _differs(fr.world(i, f), m) or _other(vals, {p: v.get(p) for p in keyed[i]}) or \
                    (bs is not None and any(_differs(x, y) for x, y in zip(pose(i, f), bs))):
                return f, i
    return None


def _sim_end(data, info, folder, fr) -> tuple[int, str] | None:
    """The last frame a cloth's points or a falling copy still move (the stored result); None when none do."""
    from .sim.cloth_check import frames_of
    from .sim.fall_view import _paths
    from .sim.inputs import bodies, value
    from .sim.sim_faults import _where
    if not any(value(b, "simulate") in ("cloth", "falls") for b in bodies(data)) or (where := _where(data, info, folder)) is None:
        return None
    s0, best = info["start"], None
    for item in bodies(data):
        if value(item, "simulate") != "cloth":
            continue
        try:
            n, nf, raw = frames_of(where, item["id"])
        except OSError:
            continue
        idx = range(0, n, max(1, n // 200))
        last = [raw[(nf - 1) * n * 3 + 3 * j:(nf - 1) * n * 3 + 3 * j + 3] for j in idx]
        for i in range(nf - 1, -1, -1):
            if any(math.dist(raw[i * n * 3 + 3 * j:i * n * 3 + 3 * j + 3], q) > MOVE_M for j, q in zip(idx, last)):
                best = max(best or (s0, ""), (s0 + i, item["id"]))      # the cloth's frames are the shot's from its start
                break
    for id_, p in _paths(data, info, folder, where, fr).items():
        if p.get("kind") != "copies":
            continue
        for track in p["tracks"]:
            f = next((s0 + i for i in range(len(track) - 1, -1, -1) if math.dist(track[i], track[-1]) > MOVE_M), None)
            if f is not None:
                best = max(best or (s0, ""), (f, id_))
    return best


def _can_move(fr, id_: str, sim: dict | None) -> bool:
    """Keyed, posed, aimed, following, stuck, a rig, simulated, or inside something that is."""
    it = fr.items[id_]
    if it.get("keys") or it["type"] == "rig" or it.get("aim", "none") != "none" or it.get("follow") or it.get("stick")             or (sim and id_ in sim.get("moves", {})) or any(b.get("keys") for b, _ in skin.bones_of(it)):
        return True
    return bool(fr.parent.get(id_)) and _can_move(fr, fr.parent[id_], sim)


def frozen_end(data: dict, info: dict, folder=None, sim: dict | None = None, fr=None) -> list[dict]:
    """[the frozen_end fault] or []. `fr`: the look's resolved Frames when they cover the whole shot (shared cache)."""
    from .motion_track import Track
    s0, s1, fps = info["start"], info["end"], info["fps"]
    if (s1 - s0) / fps <= STILL_S:
        return []
    if fr is None or fr.frames.start > s0 or fr.frames.stop <= s1:
        fr = Track(data, info, range(s1, s1 + 1), folder, sim).fr     # its Frames cover the whole shot; one camera
    ids = [i for i in fr.items if fr.items[i]["type"] != "material" and _can_move(fr, i, sim)]
    frames = list(range(s0, s1, STEP))
    last = _last_change(fr, ids, frames, s1)
    try:
        moved = _sim_end(data, info, folder, fr)
    except Exception:  # noqa: BLE001
        moved = None
    if moved and (last is None or moved[0] > last[0]):
        last = moved
    f = min(s1, last[0] + STEP) if last else s0                      # the first frame that matches the end
    still = (s1 - f) / fps
    if still <= STILL_S:
        return []
    x, end = (f - s0) / fps, (s1 - s0) / fps
    what = (f"nothing moves from {x:.1f} s to the end ({still:.1f} s still"
            + (f"; the last thing moving is {last[1]})" if last else "; nothing in the shot moves at all)"))
    return [F.fault(f"frozen_end:{info['id']}", what,
                    "carry the action or a small settle/idle (breath, head tilt, slow camera push) to the last frame, or end "
                    f"the shot at {min(x + 0.5, end):.1f} s; keep it only if the brief asks for a hold",
                    f"frame {f}, {x:.2f} s")]
