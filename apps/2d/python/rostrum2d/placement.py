"""Composition px <-> a layer's own px and its paint canvas px: the ONE mapping painting uses, the engine's own
(ENGINE_CONTRACT.md § 1 `place`). The engine lays the frame out and gives each layer's own px -> comp px as a 3×3
projective matrix through its parent groups, the camera and 3D tilt, the very transform it draws with; here it is only
inverted. The screen's pen (screen2d/strokes.py) and the operations' composition-px points (paint.stroke, paint.fill
with `space: "comp"`) both go through `canvas_points`, so a stroke lands under the pointer wherever the layer sits.

A place is {"m": [9 numbers], "w", "h": the layer's own box (its paint is stretched over it), "edge": path data}.
`place_at` asks an engine for one from a document (no screen): this module's own engine, started on first use and
closed when Python exits, loaded with the document's scene. No engine built -> EngineError, loudly: no estimate.
"""
from __future__ import annotations

import atexit
import threading

from . import drawing as D

_lock = threading.RLock()
_own = None                 # this module's own engine (place_at)


def comp_point(place: dict, lx: float, ly: float) -> tuple[float, float]:
    """A point in the layer's own px -> comp px."""
    m = place["m"]
    w = m[6] * lx + m[7] * ly + m[8]
    return (m[0] * lx + m[1] * ly + m[2]) / w, (m[3] * lx + m[4] * ly + m[5]) / w


def own_point(place: dict, x: float, y: float) -> tuple[float, float]:
    """A comp px point -> the layer's own px (the inverse of the projective matrix; a layer turned edge-on or scaled to
    nothing has no own point: ValueError)."""
    a, b, c, d, e, f, g, h, i = place["m"]
    # The adjugate: m^-1 up to a factor, which the divide by w' cancels.
    A, B, C = e * i - f * h, c * h - b * i, b * f - c * e
    D_, E, F = f * g - d * i, a * i - c * g, c * d - a * f
    G, H, I = d * h - e * g, b * g - a * h, a * e - b * d
    w = G * x + H * y + I
    if abs(a * A + b * D_ + c * G) < 1e-12 or abs(w) < 1e-12:
        raise ValueError("the layer is turned edge-on or scaled to nothing here; there is no point on it")
    return (A * x + B * y + C) / w, (D_ * x + E * y + F) / w


def canvas_points(item: dict, props: dict, place: dict, points) -> list[list[float]]:
    """[[x, y, *rest], …] in comp px -> the item's paint canvas px (rest, e.g. pressure, kept), rounded to 0.01. Canvas
    px count pixel centres (the painting kit draws pixel i's centre at canvas i), own px run edge to edge: half a pixel
    apart."""
    cw, ch = D.paint_size(item, props)
    w, h = place["w"], place["h"]
    if not w or not h:
        raise ValueError(f'{item["id"]} has no size here; there is no canvas point on it')
    out = []
    for q in points:
        lx, ly = own_point(place, q[0], q[1])
        out.append([round(lx * cw / w - 0.5, 2), round(ly * ch / h - 0.5, 2), *q[2:]])
    return out


def _comp_of(doc_data: dict, layer_id: str) -> str:
    def has(layers):
        return any(lay["id"] == layer_id or has(lay.get("layers", [])) for lay in layers)
    for c in doc_data.get("comps", []):
        if has(c.get("layers", [])):
            return c["id"]
    raise KeyError(f"no layer {layer_id!r} in any composition")


def open_engine():
    """The engine `place_at` starts when it first needs one (tests swap this)."""
    from .engine import Engine
    return Engine()


def place_at(doc_data: dict, layer_id: str, t: float) -> dict:
    """The layer's place at composition time `t`, from the document as it is (a document's own operations have no
    screen; the scene is described without the project's markers and 3D renders, as only the layer's place is read)."""
    global _own
    from .scene import describe
    scene = describe(doc_data, _comp_of(doc_data, layer_id), None, None, (t, t))
    with _lock:
        if _own is None:
            _own = open_engine()
            atexit.register(_own.close)
        _own.load(scene)
        return _own.place(t, [layer_id])[layer_id]
