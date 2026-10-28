"""Where a cloth starts and ends, for run_simulation's reply (critic 3d-final: an agent's cloth landed beside the objects and the
reply said "0 falling", so nothing warned it), and `over`: a sheet placed over the thing it should drape (sim.body over=).

    lines, facts = report(doc.data, info, res_folder)      # per cloth: what it ends on, and a warning when it misses
    values = over(doc.data, sheet_item, "box")             # x y z (and width / depth when too small) for the sheet

A cloth's stored points are in its own space at the first frame (result.py); they go through its world place there. A point
"rests on" a body when it is within REACH of that body's box at the last frame and above the ground; a cloth that touches no
body at the end, or whose middle ends farther sideways than a third of its size from where it started, is named in a warning.
"""
from __future__ import annotations

import array
import struct
import sys
from pathlib import Path

from .. import aim
from ..resolve import Frames
from .inputs import bodies, value
from .result import CLOTH_HEADER, cloth_file

REACH = 0.03            # m: a cloth point this close to a body's box rests on it
ABOVE = 0.1             # how far over the top `over` puts the sheet, as a share of the thing's height (at least MIN_ABOVE)
MIN_ABOVE = 0.05        # m
COVER = 2.0             # a sheet smaller than the thing's footprint × 1.25 is made this many times its footprint


def frames_of(folder, item: str) -> tuple[int, int, array.array]:
    """(points, frames, float32 x y z per point per frame) of a stored cloth, its own space."""
    raw = (Path(folder) / cloth_file(item)).read_bytes()
    n, t, fr, _ = struct.unpack("<4i", raw[4:CLOTH_HEADER])
    a = array.array("f")
    a.frombytes(raw[CLOTH_HEADER + 12 * t + 8 * n:])
    if sys.byteorder != "little":
        a.byteswap()
    return n, fr, a


def _box(data: dict, id_: str, t: float):
    from ..item_bounds import world_box
    try:
        return world_box(data, [id_], t)
    except Exception:  # noqa: BLE001  an import or an empty group has no box here: it is just not counted
        return None


def _inside(p, box, reach=REACH) -> bool:
    lo, hi = box
    return all(lo[k] - reach <= p[k] <= hi[k] + reach for k in range(3))


def report(data: dict, info: dict, folder) -> tuple[list[str], list[str], list[dict]]:
    """(reply parts, warnings, facts) for each cloth in the stored result at `folder`."""
    s0, s1, fps = info["start"], info["end"], info["fps"]
    fr = Frames(data, range(s0, s0 + 1), fps)
    others = [b for b in bodies(data) if value(b, "simulate") != "cloth"]
    ground = bool(_shot(data, info["id"]).get("simGround", True))
    parts, warns, facts = [], [], []
    for item in (b for b in bodies(data) if value(b, "simulate") == "cloth"):
        id_ = item["id"]
        try:
            n, nf, pts = frames_of(folder, id_)
        except OSError:
            continue
        place = fr.world(id_, s0)
        first = [aim.point(place, pts[3 * i:3 * i + 3]) for i in range(n)]
        o = (nf - 1) * n * 3
        last = [aim.point(place, pts[o + 3 * i:o + 3 * i + 3]) for i in range(n)]
        ends = (s1 - s0) / fps
        boxes = {b["id"]: bx for b in others if (bx := _box(data, b["id"], ends)) is not None}
        on = sorted(b for b, bx in boxes.items() if sum(_inside(p, bx) for p in last) >= max(3, n // 200))
        size = max(max(p[k] for p in first) - min(p[k] for p in first) for k in (0, 2)) or 1.0
        mid0 = [sum(p[k] for p in first) / n for k in (0, 2)]
        mid1 = [sum(p[k] for p in last) / n for k in (0, 2)]
        slid = ((mid1[0] - mid0[0]) ** 2 + (mid1[1] - mid0[1]) ** 2) ** 0.5
        under = sorted(b for b, bx in ((b["id"], _box(data, b["id"], 0.0)) for b in others) if bx is not None and any(
            bx[0][0] <= p[0] <= bx[1][0] and bx[0][2] <= p[2] <= bx[1][2] and p[1] >= bx[1][1] - REACH for p in first))
        on_ground = ground and sum(p[1] < REACH for p in last)
        parts.append(f"cloth {id_}: {n} points, ends on {', '.join(on) if on else 'nothing but the ground' if on_ground else 'nothing'}")
        facts.append({"item": id_, "points": n, "endsOn": on, "startsOver": under, "slidM": round(slid, 3),
                      "onGround": bool(on_ground)})
        fix = (f'place it over what it should cover (sim.body kind=cloth over="<item>", or the script\'s '
               f'.simulate("cloth", over=<item>)), and check that thing is set to Stays still')
        if not under:
            warns.append(f"Cloth {id_} does not start over anything it can land on (nothing set to Falls or Stays still is "
                         f"under it at the first frame), so it only falls{' to the ground' if ground else ''}: {fix}.")
        elif not on:
            warns.append(f"Cloth {id_} started over {', '.join(under)} but ends touching "
                         f"{'only the ground' if on_ground else 'nothing'}: it slid off ({slid:.2f} m sideways). Look at "
                         f"it with look_sheet; a heavier, stiffer or shorter cloth (clothWeight, stiffness, a smaller "
                         f"sheet that does not reach the ground) stays on better.")
        elif slid > size / 3:
            warns.append(f"Cloth {id_} moved {slid:.2f} m sideways while falling (a third of its size or more): it may "
                         f"hang off one side of {', '.join(on)}; look at it with look_sheet.")
    return parts, warns, facts


def _shot(data: dict, shot_id: str) -> dict:
    from ..compile import _shot as shot
    return shot(data, shot_id)


def over(data: dict, sheet: dict, target: str) -> dict:
    """Fields that put a sheet over `target` at the first frame: centred over its box, its lowest point a little above
    the top (ABOVE of its height, at least MIN_ABOVE), unturned; a plane smaller than 1.25 × the footprint's larger side
    is made COVER × that side, square. ValueError when the target has no box (an import)."""
    box = _box(data, target, 0.0)
    if box is None:
        raise ValueError(f'"{target}" has no size the drape can measure (an import or an empty group)')
    (lx, ly, lz), (hx, hy, hz) = box
    out = {"x": round((lx + hx) / 2, 4), "z": round((lz + hz) / 2, 4), "rx": 0.0, "ry": 0.0, "rz": 0.0,
           "y": round(hy + max(MIN_ABOVE, ABOVE * (hy - ly)), 4)}
    foot = max(hx - lx, hz - lz)
    if sheet.get("shape") == "plane" and min(float(sheet.get("width", 1.0)) * float(sheet.get("sx", 1.0)),
                                             float(sheet.get("depth", 1.0)) * float(sheet.get("sz", 1.0))) < 1.25 * foot:
        side = round(COVER * foot, 4)
        out.update(width=side / float(sheet.get("sx", 1.0)), depth=side / float(sheet.get("sz", 1.0)))
    return out
