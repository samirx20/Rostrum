"""PSD layer masks → what the app has. A pixel mask that is a plain box, and a vector mask that is a rectangle or an ellipse,
become real masks (`mask` items: rect / ellipse). Anything freer (a painted or soft pixel mask, a free-form vector path, any
mask on a group) becomes a track matte: a hidden layer beside the masked one that the masked layer is seen through (a grey
picture of the mask, or the path itself). Mask boxes are in the layer's own px from its top-left corner.

`masks_for` → {"masks": [mask props], "matte": node | None, "mode": matteMode}, or None when the layer's masks can't be
carried (two that both need a matte; reported), and the caller keeps the baked pixels.
"""
from __future__ import annotations

import numpy as np
from PIL import Image

from .psd_shape import _d

_EDGE = 0.5          # px: how close a knot may be to a rectangle's corner / an ellipse's edge middle


def _rect(box, layer_box, invert: bool) -> dict | None:
    """The mask's rect (page px) as mask props in the layer's px; None for a plain mask that covers the whole layer (no effect)."""
    x0, y0, x1, y1 = box
    lx, ly, lw, lh = layer_box
    if not invert and x0 <= lx and y0 <= ly and x1 >= lx + lw and y1 >= ly + lh:
        return None
    return {"shape": "rect", "x": float(x0 - lx), "y": float(y0 - ly), "w": float(x1 - x0), "h": float(y1 - y0), "invert": invert}


def _box_mask(m) -> tuple | None:
    """(box, invert) for a pixel mask that is solid inside its box over a flat outside; else None."""
    img = m.topil()
    if img is None:
        return None
    a = np.asarray(img.convert("L"))
    if a.size and a.min() == 255 and m.background_color == 0:
        return m.bbox, False
    if a.size and a.max() == 0 and m.background_color == 255:
        return m.bbox, True
    return None


def _pixel_matte(layer, m) -> dict | None:
    """The mask as a grey picture covering the layer and the mask (outside the mask: its background colour)."""
    img = m.topil()
    if img is None:
        return None
    l, t, r, b = layer.bbox
    x0, y0 = min(l, m.left), min(t, m.top)
    x1, y1 = max(r, m.right), max(b, m.bottom)
    grey = Image.new("L", (x1 - x0, y1 - y0), m.background_color)
    grey.paste(img.convert("L"), (m.left - x0, m.top - y0))
    return {"type": "image", "name": f"{layer.name} mask", "box": [x0, y0, x1 - x0, y1 - y0], "image": grey.convert("RGBA"),
            "props": {"fit": "stretch"}}


def _vector_shape(vm, w: int, h: int) -> dict | None:
    """Mask props (page px) when a one-path vector mask is an axis-aligned rectangle or an ellipse."""
    if len(vm.paths) != 1 or not vm.paths[0].is_closed() or len(vm.paths[0]) != 4:
        return None
    knots = list(vm.paths[0])
    pts = [(k.anchor[1] * w, k.anchor[0] * h) for k in knots]
    x0, x1 = min(p[0] for p in pts), max(p[0] for p in pts)
    y0, y1 = min(p[1] for p in pts), max(p[1] for p in pts)
    box = {"x": x0, "y": y0, "w": x1 - x0, "h": y1 - y0}
    if not any(k.leaving != k.anchor for k in knots):
        flat = len({round(p[0] / _EDGE) for p in pts}) == 2 and len({round(p[1] / _EDGE) for p in pts}) == 2
        return {"shape": "rect", **box} if flat else None
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return {"shape": "ellipse", **box} if all(abs(p[0] - cx) < _EDGE or abs(p[1] - cy) < _EDGE for p in pts) else None


def _path_matte(layer, vm, w: int, h: int) -> dict:
    d, box = _d(vm.paths, w, h)
    return {"type": "path", "name": f"{layer.name} mask", "box": box,
            "props": {"d": d, "filled": True, "fill": "#ffffff", "fillRule": "nonzero"}}


def masks_for(layer, node_box, size: tuple, report: list, group: bool = False) -> dict | None:
    name, masks, matte, mode = layer.name, [], None, "alpha"
    if layer.has_mask():
        m = layer.mask
        if m.disabled:
            report.append(f"layer '{name}': its pixel mask is switched off in the PSD; left out")
        else:
            got = None if group else _box_mask(m)
            if got:
                rect = _rect(got[0], node_box, got[1])
                masks += [rect] if rect else []
            elif (matte := _pixel_matte(layer, m)) is not None:
                mode = "luma"
                report.append(f"layer '{name}': its pixel mask is a picture, carried as a track matte layer '{name} mask'")
            else:
                report.append(f"layer '{name}': its pixel mask could not be read; baked into the pixels")
                return None
    if layer.has_vector_mask() and layer.kind != "shape":
        vm = layer.vector_mask
        if vm.disabled:
            report.append(f"layer '{name}': its vector mask is switched off in the PSD; left out")
        else:
            shape = None if group else _vector_shape(vm, *size)
            if shape:
                masks.append({**shape, "x": shape["x"] - node_box[0], "y": shape["y"] - node_box[1], "invert": vm.inverted})
            elif matte is not None:
                report.append(f"layer '{name}': a pixel mask and a free-form vector mask together; baked into the pixels")
                return None
            else:
                matte, mode = _path_matte(layer, vm, *size), "alphaInverted" if vm.inverted else "alpha"
                report.append(f"layer '{name}': its vector mask is carried as a track matte layer '{name} mask'")
    return {"masks": masks, "matte": matte, "mode": mode}
