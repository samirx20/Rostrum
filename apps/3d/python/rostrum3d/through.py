"""Looking through a light (H21): from where the light stands, along the way it shines (its −Z), to aim it by eye.
Read from the compiled scene (compile.describe) at a frame with aim.py's transforms, so the view follows the light
however it is placed, animated or aimed. The view is level (no roll), like an aimed item. Used by the screen's
viewport (app/screen3d/viewcam.py) and by MCP look_frame `through`.
"""
from __future__ import annotations

import math

from . import aim, fields as F

FOV = 60.0                                            # vertical, degrees
AIMABLE = ("rect", "disk", "strip", "sphere", "spot", "distant")
CAMERA_ID = "rostrum_through_light"
_SENT = [p for p in F.FIELDS["camera"] if p.name not in ("aim", "aimX", "aimY", "aimZ", "aimItem")]


def find_item(scene: dict, id_: str, frame: int):
    """(world transform, props at `frame`, node) of the scene item `id_`; ValueError when it is not there."""
    first = scene["shot"]["start"]
    stack = [(n, aim.IDENTITY) for n in scene.get("items", [])]
    while stack:
        node, parent = stack.pop()
        v = dict(node["props"])
        for k, vals in node.get("anim", {}).items():
            v[k] = vals[max(0, min(len(vals) - 1, frame - first))]
        world = aim.compose(parent, aim.local(v))
        if node["id"] == id_:
            return world, v, node
        stack += [(c, world) for c in node.get("children", [])]
    raise ValueError(f'no item "{id_}" in the scene')


def aimable(scene: dict, id_: str) -> bool:
    try:
        _, v, node = find_item(scene, id_, scene["shot"]["start"])
    except ValueError:
        return False
    return node["type"] == "light" and v["kind"] in AIMABLE


def light_view(scene: dict, light: str, frame: int) -> dict:
    """{eye, target, fov}: the light's world position, a point 1 m (or as far as the world origin) along its −Z."""
    world, v, node = find_item(scene, light, frame)
    if node["type"] != "light" or v["kind"] not in AIMABLE:
        kind = v.get("kind", node["type"]) if node["type"] == "light" else node["type"]
        raise ValueError(f'"{light}" is a {kind}; look through a light: {", ".join(AIMABLE)}')
    eye = aim.point(world, [0.0, 0.0, 0.0])
    ahead = [a - e for a, e in zip(aim.point(world, [0.0, 0.0, -1.0]), eye)]
    n = math.hypot(*ahead) or 1.0
    forward = [x / n for x in ahead]
    along = -sum(e * f for e, f in zip(eye, forward))                       # nearest the world origin on the line
    dist = along if along > 1e-3 else 1.0
    fov = min(max(v["cone"] * 1.25, 10.0), 150.0) if v["kind"] == "spot" else FOV    # a spot: its whole pool in view
    return {"eye": eye, "target": [e + dist * f for e, f in zip(eye, forward)], "fov": fov}


def as_camera(scene: dict, light: str, frame: int, aspect: float) -> dict:
    """A scene camera item standing where `light_view` looks from, for renders (which need a scene camera)."""
    view = light_view(scene, light, frame)
    rx, ry, rz = aim.aim_rotation(aim.IDENTITY, view["eye"], view["target"])
    sensor = 36.0
    focal = sensor / max(aspect, 1e-6) / (2 * math.tan(math.radians(view["fov"] / 2)))
    props = {p.name: p.default for p in _SENT}
    props.update(dict(zip(("x", "y", "z"), view["eye"])), rx=rx, ry=ry, rz=rz, sensorWidth=sensor, focalLength=focal)
    return {"id": CAMERA_ID, "type": "camera", "props": {k: round(x, 6) if isinstance(x, float) else x
                                                          for k, x in props.items()}}
