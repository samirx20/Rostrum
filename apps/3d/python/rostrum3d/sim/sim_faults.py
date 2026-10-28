"""faults.py for simulated things the shape boxes don't follow: a cloth's points and each copy of a falling copies item,
where the shot's stored result has them, against the shot camera's picture at the sampled frames. A cloth cut by the
frame edge; copies that end on or past the edge at the last frame looked at (a copy's centre within COPY_EDGE of it: half of it is cut).

    lines = sim_faults(doc.data, info, folder, [0, 10, 20], at=None)   # [(weight, line)]
"""
from __future__ import annotations

from rostrum_core.cache import CACHE

from .. import aim
from ..motion_track import Camera
from ..resolve import Frames
from . import fields as SF
from .cloth_check import frames_of
from .inputs import KIND, bodies, shot_value, value
from .state import state

COPY_EDGE = 0.03        # share of the picture's height: a copy's centre this close to an edge is cut by it


def _where(data: dict, info: dict, folder):
    st = state(data, info["id"], folder)
    key = {"stored": st.get("key"), "out of date": st.get("storedKey")}.get(st["state"])
    return CACHE.get(KIND, key) if key else None


def sim_faults(data: dict, info: dict, folder, fs: list[int], at: int | None = None) -> list[tuple[float, str]]:
    from ..faults import _when, edges
    things = [b for b in bodies(data) if value(b, "simulate") in ("cloth", "falls")]
    if not things or (where := _where(data, info, folder)) is None:
        return []
    check = [at] if at is not None else fs
    s0, s1 = info["start"], info["end"]
    fr = Frames(data, range(s0, s1 + 1), info["fps"], folder)
    cams = {f: Camera(fr, info["camera"], f, info["width"], info["height"]) for f in check}
    out = []
    for item in things:
        id_ = item["id"]
        if value(item, "simulate") == "cloth":
            pts = _cloth(data, info, where, fr, id_, check)
            seen = {f: edges(cams[f], p) for f, p in pts.items()}
            cut = [f for f, s in seen.items() if s[0] == "part"]
            if cut:
                sides = sorted({e for f in cut for e in seen[f][1]}) or ["edge"]
                out.append((1 + len(cut) / len(seen), f"Cloth {id_} is cut by the frame edge ({'/'.join(sides)}) from "
                            f"{_when(info, cut[0])} ({len(cut)} of {len(seen)} looks). Frame the whole drape: move the "
                            "camera back or widen the lens (shot.frame on it after the simulation)."))
        elif item["type"] == "copies":
            out += _copies(data, info, where, fr, cams, id_, check)
    return out


def _cloth(data, info, where, fr, id_, check) -> dict[int, list]:
    from ..compile import _shot
    try:
        n, nf, raw = frames_of(where, id_)
    except OSError:
        return {}
    step = SF.TIMINGS[shot_value(_shot(data, info["id"]), "simTiming")]
    place, s0, out = fr.world(id_, info["start"]), info["start"], {}
    for f in check:
        i = min(max(((f - s0) // step) * step, 0), nf - 1)
        o = i * n * 3
        out[f] = [aim.point(place, raw[o + 3 * j:o + 3 * j + 3]) for j in range(0, n, max(1, n // 400))]
    return out


def _copies(data, info, where, fr, cams, id_, check) -> list[tuple[float, str]]:
    from ..faults import _when
    from .fall_view import _paths
    p = _paths(data, info, None, where, fr).get(id_)
    if not p or p.get("kind") != "copies":
        return []
    s0, out = info["start"], []
    for f in check[-1:]:                                   # where they end up (a pour enters past the top edge on its way)
        cam, edge = cams[f], COPY_EDGE * info["height"]
        hit = {}
        for track in p["tracks"]:
            q = cam.project(track[min(max(f - s0, 0), len(track) - 1)])
            inside_before = any((r := cam.project(track[min(max(g - s0, 0), len(track) - 1)])) and 0 <= r[0] <= cam.w and 0 <= r[1] <= cam.h
                                for g in range(s0, f + 1, max(1, (f - s0) // 8 or 1)))
            if q is None or not inside_before:
                continue
            for side, d in (("left", q[0]), ("right", cam.w - q[0]), ("top", q[1]), ("bottom", cam.h - q[1])):
                if d < edge:
                    hit[side] = hit.get(side, 0) + 1
                    break
        if hit:
            side = max(hit, key=hit.get)
            n = sum(hit.values())
            out.append((1 + n / max(len(p["tracks"]), 1), f"{n} cop{'y' if n == 1 else 'ies'} of {id_} on or past the frame "
                        f"edge ({'/'.join(sorted(hit))}, most at the {side}) at {_when(info, f)}: cut by the picture. Aim the pour "
                        "or the camera so they land well inside the picture."))
    return out
