"""review's never-on-screen subject: a group, picture, video or drawing that shows (in its time, opaque) yet never once
enters the picture. edge_cut names a subject mostly in and cut by an edge and leaves one fully out alone on purpose (a
layer waiting to slide in); this is its other half, over the whole film: out at every moment it shows is never seen.
Film 2d-why-still-broken: a robot arm (group arm_assembly, opaque, in time 32-44 s) sat wholly left of the frame and
nothing said so. Measured where it really draws (its showing layers, review_blocks), in picture px with the camera.
Only the outermost one is named (the arm, not its claw)."""
from __future__ import annotations

from . import edge_cut, review_blocks as rb
from .geometry import drawn_box
from .review_sample import Sampled

KINDS = ("group", "image", "video", "drawing")
OPAQUE = 0.5              # it counts as showing from this opacity
LEAST = 1.0               # s it shows before its never being seen is named


def _extents(nodes: list[dict]) -> dict[str, tuple]:
    """{layer id: the picture box it draws in}: each showing layer's box added to it and to every group it is in."""
    out: dict[str, list] = {}
    for n in nodes:
        if rb.shows(n):
            b = drawn_box(n)
            for k in (n["id"], *n["within"]):
                e = out.setdefault(k, list(b))
                e[:] = min(e[0], b[0]), min(e[1], b[1]), max(e[2], b[2]), max(e[3], b[3])
    return {k: tuple(v) for k, v in out.items()}


def facts(s: Sampled) -> list[dict]:
    shown: dict[str, list] = {}                 # id -> [times it shows]
    span: dict[str, list] = {}                  # id -> its box over all those times
    within, ever_in = {}, set()
    for t, nodes in s.frames:
        ext = _extents(nodes)
        for n in nodes:
            e = ext.get(n["id"])
            if (n["type"] not in KINDS or not e or not n["in_time"] or n["opacity"] < OPAQUE or edge_cut.soft(n["layer"])
                    or n["type"] == "group" and not n["layer"].get("layers")):
                continue
            if min(e[2], s.W) - max(e[0], 0) > 2 and min(e[3], s.H) - max(e[1], 0) > 2:
                ever_in.add(n["id"])
                continue
            shown.setdefault(n["id"], []).append(t)
            b = span.setdefault(n["id"], list(e))
            b[:] = min(b[0], e[0]), min(b[1], e[1]), max(b[2], e[2]), max(b[3], e[3])
            within[n["id"]] = n["within"]
    named = {k for k, ts in shown.items() if k not in ever_in and len(ts) * s.step >= LEAST - 1e-9}
    out = []
    for k in named:
        if set(within[k]) & named:
            continue                            # its group is named: one line for the whole thing
        ts, (x0, y0, x1, y1) = shown[k], span[k]
        t0, t1 = round(ts[0], 2), round(ts[-1] + s.step, 2)
        where = f'"{within[k][-1]}" px' if within[k] else "the composition's px"
        out.append({"kind": "off_screen", "start": t0, "end": t1, "id": k, "ids": [k],
                    "text": f'{t0:g}–{t1:g} s: "{k}" is never on screen: it shows the whole time entirely outside the '
                            f'{s.W} × {s.H} picture (it sits at x {x0:.0f}…{x1:.0f}, y {y0:.0f}…{y1:.0f} in the picture): '
                            f'move it into the frame (its x / y are in {where}) or take it out if it is not meant to show'})
    return out
