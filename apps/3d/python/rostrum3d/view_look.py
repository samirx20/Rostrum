"""Looking from somewhere else, and where a part goes on the picture (MCP look_frame `view`, look_motion `path`).

A view is a camera that is never in the document: `{"from": [x, y, z], "to": [x, y, z] or a part}`, or orbit-style
`{"around": part, "turn_deg", "tilt_deg", "distance"}` (a part as below) (turn walks round the item to the shot camera's right, tilt
looks from higher up, both from where the shot camera stands; distance default the shot camera's own), with
`lens_mm` (default the shot camera's lens). It is placed at one frame, read from the document as the compiler
resolves it (resolve.Frames), level like an aimed item. `as_camera` makes it a scene camera for a render (the
document's compiled scene gets a copy with it added; through.py does the same for a light), `projector` measures
through it the way motion_track.Camera measures through the shot camera.

A part is an item id, or a clay figure's joint "<clay>.<joint>" (`buddy.hand.L`): the joint's bone end (where the
part ends: a hand's tip, an arm's elbow; a bone with no length its joint), carried by its pose and the clay's move.
"""
from __future__ import annotations

import math

from . import aim, pose_body as PB, skin
from .motion_track import Camera, _unit
from .through import _SENT

CAMERA_ID = "rostrum_look_view"
SENSOR = 36.0
KEYS = {"from", "to", "around", "turn_deg", "tilt_deg", "distance", "lens_mm"}


def item_point(fr, id_: str, f: int) -> list[float]:
    """An item's pivot in the world at frame f (motion_track.Track.row's `world`)."""
    v = fr.values(id_, f)
    return aim.point(fr.world(id_, f), [v.get(k, 0.0) for k in ("px", "py", "pz")])


def part_point(fr, part: str):
    """A function f -> world point of `part` (an item id or "<clay>.<joint>"); ValueError naming what exists."""
    if part in fr.items:
        return lambda f: item_point(fr, part, f)
    owner, _, joint = part.partition(".")
    if owner not in fr.items:
        raise ValueError(f'no item or joint "{part}" (a joint is "<clay>.<joint>", e.g. "buddy.hand.L")')
    from .pose_ik import Rig
    from .pose_names import resolve
    item = fr.items[owner]
    chain = skin.bones_of(item)
    if not chain:
        raise ValueError(f'"{owner}" has no joints (no bones)')
    b = resolve(joint, Rig(item), f'"{owner}"')       # the pose tools' own name lookup: hand.R, "right hand", Humanoid names
    end = [0.0, float(chain[b][0].get("length", 0.0)), 0.0]
    line = [b]                                        # only the bone and the bones it hangs from move its end
    while chain[line[-1]][1] >= 0:
        line.append(chain[line[-1]][1])
    line.reverse()
    pose = skin.poser([(chain[i][0], line.index(chain[i][1]) if chain[i][1] >= 0 else -1) for i in line], fr.stack)
    ends: dict = {}                                   # held frame -> the bone end in the clay's own space

    def at(f: int) -> list[float]:
        if (g := fr.held(owner, f)) not in ends:
            ends[g] = aim.point(pose(g / fr.fps)[-1], end)
        return aim.point(fr.world(owner, f), ends[g])
    return at


def place(fr, camera: str, spec: dict, f: int) -> dict:
    """{eye, target, focal, sensor} of a view at frame f; ValueError for a view that can't stand."""
    if extra := set(spec) - KEYS:
        raise ValueError(f'unknown {", ".join(sorted(extra))}; a view takes {", ".join(sorted(KEYS))}')
    if ("from" in spec) == ("around" in spec):
        raise ValueError('give "from" (with "to") or "around", one of them')
    v = fr.values(camera, f)
    shot_eye = aim.point(fr.world(camera, f), [0.0, 0.0, 0.0])
    focal = float(spec.get("lens_mm", v["focalLength"] * SENSOR / v["sensorWidth"]))   # the same picture on a 36 mm sensor
    point = lambda x: part_point(fr, x)(f) if isinstance(x, str) else [float(c) for c in x]   # noqa: E731
    if "from" in spec:
        if "to" not in spec:
            raise ValueError('"from" needs "to": a point [x, y, z] or an item id to look at')
        eye, target = point(spec["from"]), point(spec["to"])
    else:
        target = point(spec["around"])
        d = [e - t for e, t in zip(shot_eye, target)]
        dist = float(spec.get("distance", math.hypot(*d)))
        yaw = math.atan2(d[0], d[2]) + math.radians(spec.get("turn_deg", 0.0))
        pitch = math.atan2(d[1], math.hypot(d[0], d[2])) + math.radians(spec.get("tilt_deg", 0.0))
        pitch = max(-math.radians(89.0), min(math.radians(89.0), pitch))
        eye = [target[0] + dist * math.cos(pitch) * math.sin(yaw), target[1] + dist * math.sin(pitch),
               target[2] + dist * math.cos(pitch) * math.cos(yaw)]
    if math.dist(eye, target) < 1e-6:
        raise ValueError("it stands at the point it looks at")
    return {"eye": eye, "target": target, "focal": focal, "sensor": SENSOR}


def _rotation(view: dict) -> tuple[float, float, float]:
    return aim.aim_rotation(aim.IDENTITY, view["eye"], view["target"])


def as_camera(view: dict) -> dict:
    """A scene camera item standing at the view, for a render."""
    rx, ry, rz = _rotation(view)
    props = {p.name: p.default for p in _SENT}
    props.update(dict(zip(("x", "y", "z"), view["eye"])), rx=rx, ry=ry, rz=rz, sensorWidth=view["sensor"], focalLength=view["focal"])
    return {"id": CAMERA_ID, "type": "camera", "props": {k: round(x, 6) if isinstance(x, float) else x for k, x in props.items()}}


def projector(view: dict, width: int, height: int) -> Camera:
    """motion_track.Camera standing at the view: `project(p)` -> (x px, y px) or None behind it."""
    rx, ry, rz = _rotation(view)
    lin, _ = aim.local({"x": 0, "y": 0, "z": 0, "rx": rx, "ry": ry, "rz": rz, "sx": 1, "sy": 1, "sz": 1})
    cam = Camera.__new__(Camera)
    cam.eye, cam.w, cam.h = list(view["eye"]), width, height
    cam.right, cam.up, cam.back = (_unit([row[k] for row in lin]) for k in range(3))
    cam.tan_w = view["sensor"] / (2 * view["focal"])
    cam.tan_h, cam.near = cam.tan_w * height / width, 0.01
    return cam


def words(view: dict) -> str:
    """'from (x, y, z) looking at (x, y, z), 35 mm' for a reply."""
    r = lambda p: "(" + ", ".join(f"{c:.2f}" for c in p) + ")"    # noqa: E731
    return f'from {r(view["eye"])} looking at {r(view["target"])}, {view["focal"]:.0f} mm'


def path(at, frames: list[int], cam_of, fps: float, start: int, width: int, height: int) -> dict:
    """The part's path on the picture at `frames`: per sample {t, frame, x, y} (0–1 picture units, None when behind the
    camera) and speed (picture heights per second since the last seen sample); travel (picture heights), x/y ranges."""
    rows, last, travel = [], None, 0.0
    for f in frames:
        p = cam_of(f).project(at(f))
        row = {"t": round((f - start) / fps, 4), "frame": f, "x": None, "y": None, "speed": None}
        if p:
            x, y = p[0] / width, p[1] / height
            row.update(x=round(x, 4), y=round(y, 4))
            if last:
                step = math.hypot((x - last[0]) * width / height, y - last[1])     # in picture heights
                travel += step
                row["speed"] = round(step / ((f - last[2]) / fps), 4)
            last = (x, y, f)
        rows.append(row)
    seen = [r for r in rows if r["x"] is not None]
    rng = lambda k: [min(r[k] for r in seen), max(r[k] for r in seen)] if seen else None     # noqa: E731
    speeds = [r["speed"] for r in rows if r["speed"] is not None]
    return {"samples": rows, "travel": round(travel, 4), "x": rng("x"), "y": rng("y"),
            "peak_speed": max(speeds) if speeds else 0.0, "behind": [r["t"] for r in rows if r["x"] is None],
            "outside": [r["t"] for r in seen if not (0 <= r["x"] <= 1 and 0 <= r["y"] <= 1)]}
