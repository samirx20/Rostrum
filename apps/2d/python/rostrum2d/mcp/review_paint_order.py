"""review's paint order: in one drawing, a small painted patch (a fill, or a wash inside its outline) from a LATER paint
layer that sits partly on an earlier painted shape and partly off it. Paint layers stack in the order they were made,
so the patch shows in front of that shape where they meet: Night Market (rebench 3E r1) painted the lit windows on a
"lights" layer after the washes, and they showed over the awnings in front of the houses. A patch wholly inside a shape
(a window in a wall) or wholly outside it is fine, and so is a big shape (a sky) under small ones. From the document's
points alone, nothing drawn."""
from __future__ import annotations

from rostrum2d import write_on
from rostrum2d.drawing import canvas_size, frame_at

from .review_sample import Sampled, runs

STRADDLE = (0.1, 0.9)     # share of the patch on the shape: between these it reads as partly in front
SMALLER = 0.5             # the patch is at most this share of the shape's area (a shape over a smaller one is a cover)
BACKGROUND = 0.4          # a shape this share of the canvas or bigger is a backdrop: anything may cross its edge
GRID = 9                  # points per side sampled in a patch's box


def _area(poly) -> float:
    return abs(sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1]))) / 2


def _inside(x: float, y: float, poly) -> bool:
    hit, j = False, len(poly) - 1
    for i in range(len(poly)):
        (xi, yi), (xj, yj) = poly[i], poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            hit = not hit
        j = i
    return hit


def regions(frame: dict) -> list[tuple[int, str, str, list]]:
    """[(paint layer index, region id, paint layer id, outline)] of a drawing frame's painted shapes in drawing order: each
    fill's points, and each wash's outline (its strokes share one paintmask, named once)."""
    masks = {m["id"]: [tuple(q[:2]) for q in m.get("points", [])] for m in frame.get("paintmasks", [])}
    out, seen = [], set()
    for li, paint in enumerate(frame.get("paints", [])):
        if not paint.get("visible", True):
            continue
        for s in paint.get("strokes", []):
            if s.get("type") == "fill" and len(s.get("points", [])) >= 3:
                out.append((li, s["id"], paint["id"], [tuple(q[:2]) for q in s["points"]]))
            elif s.get("mask") in masks and s["mask"] not in seen and len(masks[s["mask"]]) >= 3:
                seen.add(s["mask"])
                out.append((li, s["id"], paint["id"], masks[s["mask"]]))
    return out


def on_share(patch, shape) -> float:
    """The share of `patch` lying on `shape` (points of a grid over the patch's box that fall in the patch)."""
    xs, ys = [p[0] for p in patch], [p[1] for p in patch]
    pts = [(min(xs) + (max(xs) - min(xs)) * (i + 0.5) / GRID, min(ys) + (max(ys) - min(ys)) * (j + 0.5) / GRID)
           for i in range(GRID) for j in range(GRID)]
    pts = [p for p in pts if _inside(*p, patch)]
    return sum(_inside(*p, shape) for p in pts) / len(pts) if pts else 0.0


def crossings(frame: dict, canvas_area: float) -> list[tuple[str, str, str, str]]:
    """[(patch id, its paint layer, shape id, its paint layer)]: patches from a later paint layer half on an earlier shape."""
    regs = regions(frame)
    out, named = [], set()
    for li, pid, play, patch in regs:
        pa = _area(patch)
        for lj, sid, slay, shape in regs:
            if lj >= li or pid in named:
                continue
            sa = _area(shape)
            if sa >= BACKGROUND * canvas_area or pa > SMALLER * sa:
                continue
            if STRADDLE[0] <= on_share(patch, shape) <= STRADDLE[1]:
                out.append((pid, play, sid, slay))
                named.add(pid)              # one line per patch: the first shape it crosses
    return out


def facts(s: Sampled) -> list[dict]:
    out = []
    drawings = [layer for layer in _all_layers(s.comp.get("layers", [])) if layer.get("type") == "drawing"]
    for layer in drawings:
        shown = {}                                  # frame number -> [sample index] when the drawing shows that frame
        for i, (t, nodes) in enumerate(s.frames):
            n = next((n for n in nodes if n["id"] == layer["id"]), None)
            if n is not None and s.seen(n) and write_on.amount_at(layer, t) > 0.999:     # whole: every patch is laid
                shown.setdefault(id(frame_at(layer, n["frame"])), (frame_at(layer, n["frame"]), []))[1].append(i)
        w, h = canvas_size(layer)
        for frame, at in shown.values():
            hits = crossings(frame or {}, float(w) * float(h) or 1.0)
            if not hits:
                continue
            t0, t1, *_ = runs([i in at for i in range(len(s.times))], s.times, s.step, s.step)[0]
            pid, play, sid, slay = hits[0]
            more = f" (and {len(hits) - 1} more patches like it)" if len(hits) > 1 else ""
            out.append({"kind": "painted_over", "start": t0, "end": t1, "id": layer["id"], "ids": [layer["id"], pid, sid],
                        "text": f'{t0:g}–{t1:g} s: in drawing "{layer["id"]}", "{pid}" (paint layer "{play}") sits partly on '
                                f'"{sid}" (paint layer "{slay}") and was painted after it, so it shows in front of it{more}; '
                                f'paint it on a layer under "{slay}", or keep it wholly inside or outside that shape'})
    return out


def _all_layers(layers: list[dict]):
    for layer in layers:
        yield layer
        yield from _all_layers(layer.get("layers", []))
