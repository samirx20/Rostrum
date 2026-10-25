"""Composition px <-> a layer's own px and its paint canvas px: the ONE mapping painting uses, the engine's own
(ENGINE_CONTRACT.md § 1 `place`). The engine lays the frame out and gives each layer's own px -> comp px as a 3×3
projective matrix through its parent groups, the camera and 3D tilt, the very transform it draws with; here it is only
inverted. The screen's pen (screen2d/strokes.py) and the operations' composition-px points (paint.stroke, paint.fill
with `space: "comp"`) both go through `canvas_points`, so a stroke lands under the pointer wherever the layer sits.

A place is {"m": [9 numbers], "w", "h": the layer's own box (its paint is stretched over it), "edge": path data}.
`place_at` asks an engine for one from a document: the host's running engine when a program registered one (`use`:
the screen's canvas engine, with the project's markers and folder, so a scripted comp-px stroke starts no engine of its
own and sees what the canvas sees), else this module's own engine, started on first use and closed when Python exits.
No engine built -> EngineError, loudly: no estimate.
"""
from __future__ import annotations

import atexit
import threading

from . import drawing as D

_lock = threading.RLock()
_own = None                 # this module's own engine (own_place)
_host = None                # the running program's (`use`)


class Host:
    """A running program's side of places: `place(scene, t, ids) -> {id: place}` (the screen's canvas engine; default
    this module's own), `markers()` -> {name: seconds} and `folder()` (the project's, where 3D render layers find
    their renders) for the scene it describes. Both are asked each time, so they follow a project switch."""

    def __init__(self, place=None, markers=lambda: None, folder=lambda: None):
        self.place, self.markers, self.folder = place or own_place, markers, folder


def use(host: Host | None):
    """Places come from this host's engine from now on (None: back to this module's own engine)."""
    global _host
    _host = host


def drop(host: Host):
    """The program closing its engine: back to this module's own, unless another host took over since."""
    global _host
    if _host is host:
        _host = None


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


def comp_points(item: dict, props: dict, place: dict, points) -> list[list[float]]:
    """The other way: [[x, y, *rest], …] in the item's paint canvas px -> comp px (rest kept)."""
    cw, ch = D.paint_size(item, props)
    w, h = place["w"], place["h"]
    return [[*comp_point(place, (q[0] + 0.5) * w / cw, (q[1] + 0.5) * h / ch), *q[2:]] for q in points]


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


def own_place(scene: dict, t: float, ids: list[str]) -> dict:
    """{id: place} from this module's own engine, started on first use and closed when Python exits."""
    global _own
    with _lock:
        if _own is None:
            _own = open_engine()
            atexit.register(_own.close)
        _own.load(scene)
        return _own.place(t, ids)


def _places(doc_data: dict, layer_id: str, span: tuple[float, float], asks: list[tuple[float, list[str]]]) -> list[dict]:
    """[{id: place}] for each (t, ids) in `asks`, from one scene of the layer's composition, through the host (with its
    project's markers and folder), else this module's own engine (no program around the document: no markers or
    renders, as only places are read)."""
    from .scene import describe
    host = _host or Host()
    scene = describe(doc_data, _comp_of(doc_data, layer_id), host.markers(), host.folder(), span)
    return [host.place(scene, t, ids) for t, ids in asks]


def place_at(doc_data: dict, layer_id: str, t: float) -> dict:
    """The layer's place at composition time `t`, from the document as it is."""
    return _places(doc_data, layer_id, (t, t), [(t, [layer_id])])[0][layer_id]


def first_shown(doc_data: dict, layer_id: str) -> int | None:
    """The first frame (of the layer's composition) where the layer is drawn, looked for a tenth of a second apart,
    or None when it shows nowhere. For the refusal of painting where the layer can't be seen."""
    comp = next(c for c in doc_data["comps"] if c["id"] == _comp_of(doc_data, layer_id))
    fps, step = comp.get("fps", 30), max(1, round(comp.get("fps", 30) / 10))
    frames = range(0, max(1, round(comp.get("duration", 1) * fps)), step)
    from .engine import EngineError
    from .scene import describe
    host = _host or Host()
    scene = describe(doc_data, comp["id"], host.markers(), host.folder(), (0, comp.get("duration", 1)))
    for n in frames:
        try:
            host.place(scene, n / fps, [layer_id])
            return n
        except (KeyError, ValueError, EngineError):      # not drawn at this time: look on
            continue
    return None


def centres_at(doc_data: dict, when: dict[str, float]) -> dict[str, tuple[float, float]]:
    """Each layer's box centre in composition px, each at its own composition time (`when`: {id: seconds}), through
    its groups, the camera and tilt (the engine's `place`): one scene load for them all. layer.stagger's spatial
    orders read these, so layers in different groups compare where they are seen."""
    if not when:
        return {}
    got = _places(doc_data, next(iter(when)), (min(when.values()), max(when.values())), [(t, [i]) for i, t in when.items()])
    out = {}
    for (id_, _), places in zip(when.items(), got):
        p = places[id_]
        out[id_] = comp_point(p, p["w"] / 2, p["h"] / 2)
    return out
