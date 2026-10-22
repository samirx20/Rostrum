"""A script's group left without a size takes the box of what is inside it (as group.make and the importers do), so its
outline, its pivot and its Scale handles sit on the content, not on a 1920 x 1080 default. Layers keep their place on
screen: they move to the new top-left and the group moves with them. Only a plain group of plain layers is fitted."""
from __future__ import annotations

from . import boxes


def fit(group: dict) -> None:
    kids = [k for k in group.get("layers", []) if k["type"] != "camera"]
    if not kids or group.get("layout", "none") != "none" or any(k.get("exprs") for k in group["layers"]):
        return
    x0, y0, x1, y1 = (f(v) for f, v in zip((min, min, max, max), zip(*(boxes.box(k) for k in kids))))
    w, h = max(x1 - x0, 1.0), max(y1 - y0, 1.0)
    for k in group["layers"]:
        for prop, off in (("x", x0), ("y", y0)):
            k[prop] = round(k[prop] - off, 6)
            for key in k.get("keys", []):
                if key["prop"] == prop:
                    key["v"] = round(key["v"] - off, 6)
    left, top = group["x"] - group["anchorX"] * group["w"], group["y"] - group["anchorY"] * group["h"]
    group.update(w=w, h=h, x=left + x0 + group["anchorX"] * w, y=top + y0 + group["anchorY"] * h)
