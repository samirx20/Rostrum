"""The pose faults of a shot's posed clay figures (round 7 of the 3D gaps: judges cap a piece for these, agents never saw them),
entries of the shot's one fault list (faults.py):

  through_body:<clay>.<joint>  a part of the figure passes into another part that is not its neighbour (a waving hand through
                               the head) deeper than it did at rest; names the joint to turn and about how far (pose_touch.py).
  touches_body:<clay>.<joint>  such a part comes up against the other (within the blend) and they meet on the picture: one lump.
  face_unmatched:<a>~<b>       a mirrored pair of features (two eyes) differ in size or height, or one shows much smaller
                               on the picture: covered by a lump (a brow) or sunk by a turn (pose_face.py).
  off_body:<item>              a small thing attached to the figure (an eye, a nose, a hat) that leaves its posed surface or slides
                               over it (it rides one bone while the part it sits on turns with another).
  on_rim:<item>                such a feature seen on or past the outline of the part it sits on: as the camera sees it, beside it (pose_rim.py).
  reads_still:<clay>.<joint>   a keyed joint whose whole motion moves its part less than STILL of the picture's width: on screen it
                               shows no motion (a "wave" of 2 cm).

The figure as balls (pose_body.py), at frames every STEP_S of the shot; nothing is rendered.
"""
from __future__ import annotations

import math

from rostrum_core.mcp import faults as F

from . import aim, follow, pose_body as PB, skin
from .pose_face import face_faults
from .pose_rim import on_rim
from .pose_touch import chain as _chain, through_touch
from .pose_wave import wave_faults

STEP_S = 0.25            # frames checked: one every this many seconds
OFF = 0.5                # an attached thing off the surface, or slid, by this share of its own size
SMALL = 0.35             # attached things smaller than this share of the figure are features (eyes, a nose)
STILL = 0.025            # a keyed part moving less than this share of the picture's width reads as still


def frames(info: dict) -> list[int]:
    n = max(1, round(info["fps"] * STEP_S))
    return list(range(info["start"], info["end"] + 1, n))


def _when(info, f):
    return f"frame {f}, {(f - info['start']) / info['fps']:.2f} s"


def _keyed(item: dict) -> set[int]:
    return {n for n, (b, _) in enumerate(skin.bones_of(item)) if any(k.get("prop") in skin.TURN for k in b.get("keys", []))}


def pose_faults(track, info: dict, check: list[int]) -> list[dict]:
    out = []
    for id_ in track.ids():
        item = track.fr.items[id_]
        if item["type"] != "clay" or id_ in track.skipped or not (keyed := _keyed(item)):
            continue
        balls = PB.rest_balls(item)
        if not balls:
            continue
        fs = sorted(set(frames(info)) | set(check)) if len(check) > 1 else check
        posed = {f: PB.posed(track.fr, id_, balls, f) for f in fs}
        out += through_touch(track, info, id_, item, balls, posed, keyed)
        out += _still(track, info, id_, item, balls, posed, keyed) if len(fs) > 1 else []    # one frame can't say a whole motion is small
        out += wave_faults(track, info, id_, item, balls, posed, keyed)
        feats = _features(track, id_, balls, posed)
        out += _off_body(track, info, id_, posed, feats)
        out += on_rim(track, info, id_, item, balls, posed, [(i, own, on) for i, own, on, _ in feats])
        out += face_faults(track, info, id_, item, balls, posed, feats)
    return out


def _still(track, info, id_, item, balls, posed, keyed) -> list[dict]:
    par, names, out = PB.parents(item), PB.joint_names(item), []
    w = info["width"]
    for joint in sorted(n for n in keyed if _swings(skin.bones_of(item)[n][0])):
        moved = _moves(track, posed, balls, [n for n in range(len(par)) if joint in _chain(par, n)])
        if moved is None or moved >= STILL * w:
            continue
        f = next(iter(posed))
        out.append(F.note(f"reads_still:{id_}.{names[joint]}",
                          f"{names[joint]} is keyed but its part travels only {moved:.0f} px ({moved / w * 100:.1f} % of the "
                          "picture's width) over the shot", _when(info, f)))
    return out


def _swings(bone: dict) -> bool:
    """Keyed back and forth (a wave, a nod, a tap): some turn's key values change direction at least twice."""
    for k in skin.TURN:
        v = [x["v"] for x in sorted((x for x in bone.get("keys", []) if x.get("prop") == k), key=lambda x: x["t"])]
        d = [b - a for a, b in zip(v, v[1:]) if abs(b - a) > 1e-6]
        if sum(1 for a, b in zip(d, d[1:]) if a * b < 0) >= 2:
            return True
    return False


def _moves(track, posed, balls, bones) -> float | None:
    """The farthest any ball of these bones travels on the picture over the frames, px; None if never seen."""
    own = [i for i, (_, _, b) in enumerate(balls) if b in bones]
    if not own:
        return None
    best, seen = 0.0, False
    for i in own:
        pts = [p for p in (track.cams[f].project(now[i][0]) for f, now in posed.items() if f in track.cams) if p]
        if pts:
            seen = True
            best = max(best, math.dist((min(x for x, _ in pts), min(y for _, y in pts)), (max(x for x, _ in pts), max(y for _, y in pts))))
    return best if seen else None


def _features(track, id_, balls, posed) -> list[tuple]:
    """Small meshes on the figure at the first frame (attached to it, or just placed there): [(id, own size, the bone of the
    part it sits on, where it is then)]."""
    fr, (f0, first) = track.fr, next(iter(posed.items()))
    size = max(math.dist(p, q) + r for p, r, _ in balls for q, _, _ in balls)
    out = []
    for it in fr.items.values():
        if it["type"] != "mesh" or it["id"] in track.skipped or fr.parent.get(it["id"]) is not None                 or it.get("follow") not in (id_, "", None) or (own := _own_size(it)) is None or own > SMALL * size:
            continue
        here0 = aim.point(fr.world(it["id"], f0), [0.0, 0.0, 0.0])
        gap0, on = PB.surface_gap(first, here0)
        if gap0 <= OFF * own:
            out.append((it["id"], own, on, here0))
    return out


def _off_body(track, info, id_, posed, features) -> list[dict]:
    """A feature that later is not where the part it sits on takes it: left behind, or riding the wrong part."""
    out, fr = [], track.fr
    names = PB.joint_names(fr.items[id_])
    f0 = next(iter(posed))
    for iid, own, on, here0 in features:
        it = fr.items[iid]
        back = aim.invert(aim.compose(fr.world(id_, f0), follow.bone_move(fr, id_, on, f0)))
        for f in posed:
            here = aim.point(fr.world(iid, f), [0.0, 0.0, 0.0])
            want = aim.point(aim.compose(fr.world(id_, f), follow.bone_move(fr, id_, on, f)), aim.point(back, here0))
            if (slid := math.dist(want, here)) <= OFF * own:
                continue
            how = ("it is not attached, so it stays where it was put" if it.get("follow") != id_ else
                   "it rides the figure as a whole, not its parts (followPose off)" if not it.get("followPose") else
                   f"it rides {names[follow.nearest_bone(fr.items[id_], follow.rest_spot(fr, iid, id_))]}")
            out.append(F.note(f"off_body:{iid}", f"{iid} slides {slid * 100:.1f} cm off {id_}'s {names[on]}: {how}",
                              _when(info, f)))
            break
    return out


def _own_size(it: dict) -> float | None:
    s = it.get("shape")
    if s == "sphere":
        return float(it.get("radius", 0.1))
    if s in ("box",):
        return max(float(it.get(k, 0.1)) for k in ("width", "height", "depth")) / 2
    if s in ("cylinder", "cone", "capsule"):
        return max(float(it.get("radius", 0.1)), float(it.get("height", 0.1)) / 2)
    return None
