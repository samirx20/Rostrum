"""Which way each text in a look_frame picture reads: through the shot camera, is it left to right, not mirrored, not upside
down, or seen from behind? A text's own axes are +X (the reading direction), +Y (up) and +Z (its front face, the side the glyphs
are counter-clockwise seen from; outline.py); they are turned into the camera's right / up / toward-the-viewer axes.
"""
from __future__ import annotations

import math

from rostrum3d import aim
from rostrum3d.resolve import Frames

EDGE_ON = 0.17                    # |cos| of the angle between the viewing direction and the text's face under this: unreadable (< 10°)


def _unit(v):
    n = math.sqrt(sum(c * c for c in v)) or 1.0
    return [c / n for c in v]


def _axis(world, v):
    return [sum(world[0][i][k] * v[k] for k in range(3)) for i in range(3)]


def _dot(a, b) -> float:
    return sum(x * y for x, y in zip(a, b))


def reading(text_world, camera_world) -> dict:
    """How a text (world transform `text_world`) reads seen through a camera (`camera_world`): {reads, angle, facing, mirrored}.
    angle: degrees of the reading direction from the picture's horizontal, counter-clockwise, −180…180 (0 = left to right, level);
    facing: 1 face-on … 0 edge-on; reads: ok | tilted | upside-down | mirrored | edge-on."""
    right, up, back = (_unit(_axis(camera_world, v)) for v in ((1, 0, 0), (0, 1, 0), (0, 0, 1)))
    x, y = _axis(text_world, (1, 0, 0)), _axis(text_world, (0, 1, 0))
    sx, sy, ux, uy = _dot(x, right), _dot(x, up), _dot(y, right), _dot(y, up)
    handed = sx * uy - sy * ux                                  # > 0: on the picture, up is a quarter turn left of the reading direction
    facing = _facing(x, y, back)
    angle = math.degrees(math.atan2(sy, sx))
    mirrored = handed < 0
    flipped = aim.det(text_world[0]) < 0                        # a negative scale: the mirror is in the item, not the viewpoint
    if abs(facing) < EDGE_ON:
        reads = "edge-on"
    elif mirrored:
        reads = "mirrored"
    elif abs(angle) >= 135:
        reads = "upside-down"
    elif abs(angle) > 10:
        reads = "tilted"
    else:
        reads = "ok"
    return {"reads": reads, "angle": round(angle, 1), "facing": round(facing, 2), "mirrored": mirrored, "scaleFlipped": flipped}


def _facing(x, y, back) -> float:
    """How face-on the text's plane is to the viewer: 1 face-on … 0 edge-on (from either side)."""
    n = _unit([x[1] * y[2] - x[2] * y[1], x[2] * y[0] - x[0] * y[2], x[0] * y[1] - x[1] * y[0]])
    return abs(_dot(n, back))


def _why(r: dict) -> str:
    if r["reads"] == "mirrored":
        return ("seen from behind, so it reads mirrored" if not r["scaleFlipped"] else "mirrored by a negative scale (sx or sy below 0)")
    return {"ok": "reads left to right", "edge-on": "seen edge-on, unreadable", "upside-down": "upside down",
            "tilted": f"tilted {abs(r['angle']):g}° {'up' if r['angle'] > 0 else 'down'} to the right"}[r["reads"]]


def seen_texts(doc, info: dict, frame: int, aspect: float) -> list[dict]:
    """The text items (mesh, shape text, visible) whose middle is in front of the shot camera and inside the picture at `frame`,
    each {item, text, reads, angle, facing, why}."""
    at = round(frame / info["fps"] * 1000)
    fr = Frames(doc.data, range(at, at + 1), 1000.0)
    cam_world, cam = fr.world(info["camera"], at), fr.values(info["camera"], at)
    tan_x = cam["sensorWidth"] / 2 / cam["focalLength"]
    out = []
    for id_, item in fr.items.items():
        if item.get("type") != "mesh" or item.get("shape") != "text":
            continue
        v = fr.values(id_, at)
        if not v.get("visible", True):
            continue
        world = fr.world(id_, at)
        p = aim.point(aim.invert(cam_world), aim.point(world, [0.0, 0.0, 0.0]))
        if p[2] >= 0 or abs(p[0] / -p[2]) > tan_x * 1.05 or abs(p[1] / -p[2]) > tan_x / aspect * 1.05:
            continue
        r = reading(world, cam_world)
        out.append({"item": id_, "text": str(v.get("text", "")).replace("\n", " ")[:40], **r, "why": _why(r)})
    return out


def sentence(rows: list[dict]) -> tuple[str, dict]:
    """(' Text: "Hero" reads left to right; …', facts) for look_frame's reply; nothing when no text is in the picture."""
    if not rows:
        return "", {}
    said = "; ".join(f'"{r["text"]}" ({r["item"]}) {r["why"]}' + ("" if r["reads"] == "edge-on" else f" (angle {r['angle']:g}° to the horizontal)")
                     for r in rows)
    return f" Text reading: {said}.", {"text": rows}
