"""The crumb's shot list (SPEC §8, Job e): which shot the screen shows, and "New shot from this view".

Which shot is shown is screen state (never a document edit): Bridge3D.showShot. A new shot from the view is one
operation, `shot.from_view` (ops_scene.py), the same one agents call: a camera where the free view stands and looks,
with the focal length that frames the same height, and a shot through it. No Qt.
"""
from __future__ import annotations

import math

from rostrum3d import aim
from rostrum3d import fields as F
from rostrum3d.kind import KIND
from rostrum_core import ids
from rostrum_core.tree import index

SENSOR = F.param("camera", "sensorWidth").default      # the new camera's sensor (36 mm, full frame)


def crumb_entries(shots: list[dict], shown: str, view_mode: str, can_add: bool) -> list[dict]:
    """The crumb's list: every shot (the shown one checked), then one way to make a new one. Looking through the shot
    camera there is no new view to keep, so it offers a plain New shot (the same camera); otherwise New shot from
    this view."""
    rows = [{**s, "checked": s["value"] == shown} for s in shots]
    if view_mode != "shot":
        return rows + [{"value": "+view", "label": "New shot from this view"}]
    return rows + ([{"value": "+shot", "label": "New shot"}] if can_add else [])


def view_args(eye, target, fov: float, width: int, height: int) -> dict:
    """shot.from_view's position, turn and focal length for a view (eye, target, vertical fov in degrees) framed at
    width × height: the camera sees as much height as the view did."""
    turn = aim.aim_rotation(aim.IDENTITY, list(eye), list(target))
    sensor_h = SENSOR * height / width
    focal = sensor_h / (2 * math.tan(math.radians(fov) / 2))
    return {"position": [round(x, 6) for x in eye], "turn": [round(x, 4) for x in turn], "focalLength": round(focal, 2)}


def from_view_call(doc, cam, info: dict) -> tuple[dict, str]:
    """(the shot.from_view call, the new shot's id) for the viewport camera `cam` (viewcam.ViewCam); `info`: the
    first shot's frame size (bridge.shot_info shape)."""
    held = index(doc.data, KIND.lists)
    shot, camera = ids.counted(held, "shot"), ids.counted(held, "camera")
    args = {"id": shot, "cameraId": camera, **view_args(cam.eye, cam.target, cam.fov, info["width"], info["height"])}
    return {"op": "shot.from_view", "args": args}, shot
