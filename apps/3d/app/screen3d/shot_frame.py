"""The shot frame inside the viewport (SPEC §1.1): the shot's picture fitted in the viewport with a clear margin, and the
scene around it shown too (dimmed by the screen), never letter-boxed with empty bands.

Looking through the shot camera, the viewport asks the engine for a wider copy of that camera (`overscan`): same place,
same lens, a sensor as many times wider as the viewport is wider than the frame. The frame's part of that picture is
exactly the shot camera's picture (depth of field included); the rest is what lies just outside it. Screen only: the
copy is added to the viewport's scene, never to the document. No Qt.
"""
from __future__ import annotations

import copy

MARGIN = 16                     # screen px clear on the tighter side
VIEW_CAMERA = "rostrum_shot_view"


def fit(view_w: float, view_h: float, shot_w: float, shot_h: float, margin: float = MARGIN) -> tuple:
    """(x, y, w, h) of the shot's frame, centred in a view_w × view_h viewport, `margin` clear on the tighter side."""
    aspect = shot_w / max(shot_h, 1e-9)
    w = max(1.0, view_w - 2 * margin)
    h = w / aspect
    if h > view_h - 2 * margin:
        h = max(1.0, view_h - 2 * margin)
        w = h * aspect
    return (view_w - w) / 2, (view_h - h) / 2, w, h


def overscan(scene: dict, camera: str, factor: float) -> dict:
    """A copy of `scene` with VIEW_CAMERA beside `camera`: the same camera with a sensor `factor` times wider."""
    out = copy.deepcopy(scene)
    stack = [out.get("items", [])]
    while stack:
        siblings = stack.pop()
        for node in siblings:
            if node["id"] == camera:
                twin = copy.deepcopy(node)
                twin["id"] = VIEW_CAMERA
                twin["props"]["sensorWidth"] *= factor
                if "sensorWidth" in twin.get("anim", {}):
                    twin["anim"]["sensorWidth"] = [s * factor for s in twin["anim"]["sensorWidth"]]
                siblings.append(twin)
                return out
            stack.append(node.get("children", []))
    raise ValueError(f'viewport: no camera "{camera}" in the scene')
