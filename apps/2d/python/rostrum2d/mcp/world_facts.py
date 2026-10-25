"""Where things are in the world, from the document's values (no drawing): the frame's quad at a time and over its path,
each top-level layer's box in the world and in the picture, and how much of it the frame holds. The facts behind
look_frame (what: world), look_frame (what: in_frame), look_at {space: world} and Export › Picture › Area."""
from __future__ import annotations

from rostrum2d.frame import view

from .geometry import _apply, comp_size, flatten, problems_showing

Point = tuple[float, float]
MOVES = ("x", "y", "zoom", "rotation")


def quad(comp: dict, t: float, cam=None) -> list[Point]:
    """The frame's corners in world px at t (top-left, top-right, bottom-right, bottom-left)."""
    w, h = comp_size(comp)
    cam = cam or view.shot(comp, t)
    m = view.world_matrix(comp, cam, {"screenLock": True})
    return [_apply(m, x, y) for x, y in ((0, 0), (w, 0), (w, h), (0, h))]


def bounds(points) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def polygon(node: dict) -> list[Point]:
    """What the layer paints, as 4 points through its matrix (its whole box when it has no painted part of its own)."""
    if not node["paint"]:
        return list(node["corners"])
    x0, y0, x1, y1 = node["paint"]
    return [_apply(node["matrix"], x, y) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]


def _area(poly) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def _clip(poly, rect) -> list[Point]:
    """`poly` cut to the rectangle (x0, y0, x1, y1): Sutherland–Hodgman, one edge at a time."""
    x0, y0, x1, y1 = rect
    for axis, edge, keep in ((0, x0, 1), (0, x1, -1), (1, y0, 1), (1, y1, -1)):
        inside = lambda p: (p[axis] - edge) * keep >= 0
        out = []
        for a, b in zip(poly, poly[1:] + poly[:1]):
            if inside(a):
                out.append(a)
            if inside(a) != inside(b):
                k = (edge - a[axis]) / (b[axis] - a[axis])
                out.append((a[0] + k * (b[0] - a[0]), a[1] + k * (b[1] - a[1])))
        poly = out
        if not poly:
            break
    return poly


def share_inside(poly, width: float, height: float) -> float:
    """The part (0 to 1) of the polygon inside the picture 0..width × 0..height."""
    whole = _area(poly)
    if whole < 1e-9:                                   # a line or a point: in when the point is
        return float(all(0 <= x <= width and 0 <= y <= height for x, y in poly))
    return min(1.0, _area(_clip(poly, (0, 0, width, height))) / whole)


def in_frame(comp: dict, t: float) -> list[dict]:
    """Every top-level layer at t: its state (`in` the whole box in the picture, `partly` with the share in %, `out`), whether
    it is showing at all (and why not), its box in output px and in world px. The frame itself is not listed."""
    w, h = comp_size(comp)
    pic = [n for n in flatten(comp, t) if not n["within"]]
    world = {n["id"]: n for n in flatten(comp, t, world=True)}
    rows = []
    for n in pic:
        share = share_inside(polygon(n), w, h)
        why = problems_showing(n, w, h, frame=False)
        box = lambda poly: dict(zip(("left", "top", "right", "bottom"), (round(v, 1) for v in bounds(poly))))
        rows.append({"id": n["id"], "type": n["type"], "state": "in" if share >= 0.999 else "partly" if share > 0 else "out",
                     "share": round(share * 100), "showing": not why, "why_not_showing": why,
                     "box": box(polygon(n)), "world_box": box(polygon(world[n["id"]])), "pinned": bool(n["props"].get("screenLock"))})
    return rows


def key_times(comp: dict) -> list[float]:
    """The times the frame has a key (any of its moves)."""
    return sorted({k["t"] for k in (view.of(comp) or {}).get("keys", []) if k.get("prop") in MOVES and isinstance(k.get("t"), (int, float))})


def cuts(comp: dict) -> list[float]:
    """The times the frame jumps: each key after a hold key on one of its moves."""
    out = []
    for prop in MOVES:
        ks = sorted((k for k in (view.of(comp) or {}).get("keys", []) if k.get("prop") == prop), key=lambda k: k["t"])
        out += [b["t"] for a, b in zip(ks, ks[1:]) if a.get("ease") == "hold"]
    return sorted(set(out))


def frame_times(comp: dict) -> list[float]:
    """Every frame's time over the composition (the path's dots), at most 1000."""
    fps, n = comp.get("fps", 30), round(comp.get("duration", 5.0) * comp.get("fps", 30))
    step = max(1, -(-n // 1000))
    return [f / fps for f in range(0, n, step)]


def path_quads(comp: dict) -> list[list[Point]]:
    return [quad(comp, t) for t in frame_times(comp)]


def everything(comp: dict, t: float) -> tuple[float, float, float, float]:
    """The box round every layer as the world draws it at t and the frame's whole path (x0, y0, x1, y1)."""
    pts = [p for n in flatten(comp, t, world=True) if not n["within"] and n["in_time"] for p in polygon(n)]
    return bounds(pts + [p for q in path_quads(comp) for p in q])


def of_layers(comp: dict, ids: list[str], t: float) -> tuple[float, float, float, float]:
    """The box round the given layers as the world draws them at t."""
    nodes = {n["id"]: n for n in flatten(comp, t, world=True)}
    missing = [i for i in ids if i not in nodes]
    if missing:
        from rostrum_core.errors import RostrumError
        raise RostrumError.not_found("area", "layer", missing[0], list(nodes), "the layers of this composition")
    return bounds([p for i in ids for p in polygon(nodes[i])])


def point_in_frame(comp: dict, t: float, x: float, y: float) -> bool:
    """Is the world point (x, y) inside the frame's quad at t."""
    q = quad(comp, t)
    signs = [(b[0] - a[0]) * (y - a[1]) - (b[1] - a[1]) * (x - a[0]) for a, b in zip(q, q[1:] + q[:1])]
    return all(v >= 0 for v in signs) or all(v <= 0 for v in signs)
