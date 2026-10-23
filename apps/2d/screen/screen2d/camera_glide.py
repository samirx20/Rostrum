"""Where the camera's new view sits in the picture the person was looking at, for the canvas's short slide
(Stage.qml, ViewGlide.qml). A camera key dropped re-draws the picture through the new camera; the view slides there
instead of jumping. The view only: nothing in the document, nothing in the export."""
from __future__ import annotations

from . import motion_geo as G
from .camera_tool import active_camera


def target(bridge, held: dict) -> list[float] | None:
    """[x0, y0, x1, y1] in composition px: the new camera's frame as seen through `held` (the scene as at the press),
    or None when there is no camera or its frame is no plain box on screen."""
    cam = active_camera(bridge.placed(), bridge._t)
    if cam is None:
        return None
    t = bridge._t
    poly = G.frame_at(bridge.placed(), bridge.placed_item(cam["id"]), t, G.mapping(held, bridge.placed_item(cam["id"]), t))
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    box = [min(xs), min(ys), max(xs), max(ys)]
    return box if box[2] - box[0] > 1e-3 and box[3] - box[1] > 1e-3 else None
