"""Paint from the view (paint_fields.STROKE `viewPoints` …, LAYER `projectSource` …): what a camera saw, on a canvas.

A stroke **from the view** is kept as drawn (paint_fields.STROKE `viewPoints`, `viewEye` …; `view_of` gives them as
one dict {eye, target, fov, width, height, frame, points}): its camera, the picture's size and its points in that
picture's pixels, brush `size` in screen px. Each time the canvas is made, `lay`
turns it into the kit's strokes in canvas px from the **texel picture** of that view (texels.py: which item and which
(u, v) each pixel shows, from the engine): the path is resampled every pixel, each sample takes the (u, v) under it
(the pixels round it that show the same item on the same piece), a run ends where the path leaves the item or jumps
a seam (its canvas step far bigger than its screen step times the surface's scale there), and the brush size goes
from screen px to canvas px by that scale (canvas px per screen px, from the picture's own (u, v) steps). So moving
or reshaping the item re-lands the stroke where the camera now sees it.

A layer's projected picture (`projectSource` …; `projected_of`) is splatted the same way (`splat`): each pixel the
camera sees on the item gives its colour to the texel under it, averaged, small holes filled; what the camera
doesn't see (behind something, facing away, off the frame) stays unpainted. The texel picture for it is asked at the canvas's density or more (`project_req`).

`landed` reports where each view stroke went: [{stroke, item, layer, runs, canvasPx, offPx, share}] for agents.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

import numpy as np

VIEW_KEYS = ("eye", "target", "fov", "frame", "width", "height")
JUMP, JUMP_PX = 3.0, 4.0           # a seam: a canvas step over JUMP × (screen step × scale) + JUMP_PX
HOLES = 3                          # projection: fill holes up to this many texels across
MOST_PROJECT = 4096                # the texel picture for a projection: its long side at most this
_LOCK = threading.RLock()
_SPLATS: OrderedDict = OrderedDict()   # splat key -> (size, size, 4) float32, the last few


def view_of(stroke: dict) -> dict | None:
    """A stroke's view as one dict {eye, target, fov, width, height, frame, points}, or None (not from the view)."""
    if stroke.get("type", "stroke") != "stroke" or not stroke.get("viewPoints"):
        return None
    return {**_camera(stroke, "view"), "points": stroke["viewPoints"], **({"shot": stroke["viewShot"]}
                                                                          if stroke.get("viewShot") else {})}


def projected_of(layer: dict) -> dict | None:
    """A layer's projected picture as one dict {source, eye, target, fov, width, height, frame}, or None."""
    if not layer.get("projectSource"):
        return None
    return {"source": layer["projectSource"], **_camera(layer, "project")}


def _camera(holder: dict, prefix: str) -> dict:
    """The camera as stored (no type changes: the texel request must be the very one the screen warmed the cache
    with)."""
    w, h = holder[f"{prefix}Size"]
    return {"eye": holder[f"{prefix}Eye"], "target": holder[f"{prefix}Target"], "fov": holder[f"{prefix}Fov"],
            "width": w, "height": h, "frame": holder.get(f"{prefix}Frame") or 0}


def view_fields(view: dict) -> dict:
    """The stroke fields (viewPoints, viewEye …) for a view dict: what stroke.add takes (the screen's, agents')."""
    return {"viewPoints": [list(p) for p in view["points"]], **camera_fields(view, "view"),
            **({"viewShot": view["shot"]} if view.get("shot") else {})}


def camera_fields(view: dict, prefix: str) -> dict:
    return {f"{prefix}Eye": list(view["eye"]), f"{prefix}Target": list(view["target"]), f"{prefix}Fov": view["fov"],
            f"{prefix}Size": [int(view["width"]), int(view["height"])], f"{prefix}Frame": int(view.get("frame", 0))}


def tidy(calls: list[dict], folder=None) -> list[dict]:
    """stroke.add / stroke.set given a `view` dict (the screen's and an agent's natural form: {eye, target, fov, frame,
    width, height, points, shot?}) get its flat fields (view_fields): the core's fields hold no nested object."""
    out = []
    for c in calls:
        args = c.get("args") or {}
        if c.get("op") in ("stroke.add", "stroke.set") and isinstance(args.get("view"), dict):
            rest = {k: v for k, v in args.items() if k != "view"}
            c = {**c, "args": {**rest, **view_fields(args["view"])}}
        out.append(c)
    return out


def req_of(view: dict) -> dict:
    """The texel request (texels.py §1) for a stroke's `view` or a layer's `projected`."""
    return {k: view[k] for k in VIEW_KEYS if k in view}


def project_req(projected: dict, size: int) -> dict:
    """A projection's texel request: its camera, the picture scaled up so its long side is at least the canvas's
    (one texel picture pixel per canvas texel or finer where the item fills the frame), at most MOST_PROJECT."""
    w, h = int(projected["width"]), int(projected["height"])
    k = min(max(1.0, size / max(w, h)), MOST_PROJECT / max(w, h))
    return {**req_of(projected), "width": max(1, round(w * k)), "height": max(1, round(h * k))}


def _index(pic, item_id: str) -> int:
    return pic.items.index(item_id) if item_id in pic.items else -2


def _samples(points) -> np.ndarray:
    """The drawn path resampled every screen pixel: rows [x, y, pressure]."""
    p = np.asarray([[q[0], q[1], q[2] if len(q) > 2 else 1.0] for q in points], np.float64)
    if len(p) < 2:
        return p
    seg = np.linalg.norm(np.diff(p[:, :2], axis=0), axis=1)
    run = np.concatenate([[0.0], np.cumsum(seg)])
    n = int(min(20000, max(2, np.ceil(run[-1]) + 1)))
    at = np.linspace(0, run[-1], n)
    return np.stack([np.interp(at, run, p[:, k]) for k in range(3)], axis=1)


def _canvas(pic, size: int):
    """The texel picture's (u, v) as canvas px (x right, y down), NaN where none."""
    uv = pic.uv
    return np.stack([uv[..., 0] * size, (1.0 - uv[..., 1]) * size], axis=-1)


def _scale(cpx: np.ndarray, on: np.ndarray, ix: np.ndarray, iy: np.ndarray) -> np.ndarray:
    """Canvas px per screen px at pixels (ix, iy): the mean step to the pixels right / left and down / up on the same
    item (no seam: under 64 canvas px), sqrt of their product (a slanted surface: its mean); NaN with no neighbour."""
    h, w = on.shape

    def mean_step(pairs):
        tot, n = np.zeros(len(ix)), np.zeros(len(ix))
        for dx, dy in pairs:
            x2, y2 = np.clip(ix + dx, 0, w - 1), np.clip(iy + dy, 0, h - 1)
            d = np.linalg.norm(cpx[y2, x2] - cpx[iy, ix], axis=1)
            ok = on[y2, x2] & ((x2 != ix) | (y2 != iy)) & np.isfinite(d) & (d < 64)
            tot += np.where(ok, d, 0.0)
            n += ok
        return np.where(n > 0, tot / np.maximum(n, 1), np.nan)
    gx, gy = mean_step(((1, 0), (-1, 0))), mean_step(((0, 1), (0, -1)))
    both = np.isfinite(gx) & np.isfinite(gy)
    return np.where(both, np.sqrt(np.abs(gx * gy)), np.where(np.isfinite(gx), gx, gy))


def _look(pic, idx: int, size: int, s: np.ndarray):
    """For samples `s` (x, y in screen px): (canvas px n×2, on n bool, scale n). A sample is on the item when the
    pixel under it shows it; its canvas spot is the (u, v) of the pixels round it on the same item and piece (no
    seam between them: within JUMP_PX × 4 canvas px of the nearest), weighted by how near."""
    h, w = pic.item.shape
    cpx = _canvas(pic, size)
    on = (pic.item == idx) & np.isfinite(cpx[..., 0])
    x, y = s[:, 0] - 0.5, s[:, 1] - 0.5                 # pixel centres at +0.5
    x0, y0 = np.floor(x).astype(int), np.floor(y).astype(int)
    fx, fy = x - x0, y - y0
    nx, ny = np.clip(np.rint(s[:, 0] - 0.5).astype(int), 0, w - 1), np.clip(np.rint(s[:, 1] - 0.5).astype(int), 0, h - 1)
    inside = (s[:, 0] >= 0) & (s[:, 0] < w) & (s[:, 1] >= 0) & (s[:, 1] < h)
    hit = inside & on[ny, nx]
    near = cpx[ny, nx]
    acc, wsum = np.zeros((len(s), 2)), np.zeros(len(s))
    for dx, dy in ((0, 0), (1, 0), (0, 1), (1, 1)):
        cx, cy = np.clip(x0 + dx, 0, w - 1), np.clip(y0 + dy, 0, h - 1)
        wt = (fx if dx else 1 - fx) * (fy if dy else 1 - fy)
        c = cpx[cy, cx]
        ok = on[cy, cx] & (np.linalg.norm(np.nan_to_num(c - near, nan=1e9), axis=1) < 4 * JUMP_PX)
        wt = np.where(ok, wt, 0.0)
        acc += np.nan_to_num(c) * wt[:, None]
        wsum += wt
    spot = np.where(wsum[:, None] > 1e-9, acc / np.maximum(wsum, 1e-9)[:, None], np.nan_to_num(near))
    return spot, hit, _scale(cpx, on, nx, ny), cpx, on


def runs(stroke: dict, pic, item_id: str, size: int) -> list[dict]:
    """The stroke's runs on `item_id`: [{"points": [[x, y, pressure], …] canvas px, "size": canvas px, "screen":
    the samples' screen px (n×2)}], split where the path leaves the item or jumps a seam."""
    idx = _index(pic, item_id)
    if idx < 0:
        return []
    s = _samples(view_of(stroke)["points"])
    if not len(s):
        return []
    spot, hit, scale, _, _ = _look(pic, idx, size, s)
    fallback = np.nanmedian(scale[hit]) if np.isfinite(scale[hit]).any() else 1.0
    scale = np.where(np.isfinite(scale), scale, fallback)
    out, start = [], None
    for k in range(len(s) + 1):
        cut = k == len(s) or not hit[k]
        if not cut and start is not None and k > start:
            screen = np.linalg.norm(s[k, :2] - s[k - 1, :2])
            cut_here = np.linalg.norm(spot[k] - spot[k - 1]) > JUMP * screen * max(scale[k], scale[k - 1]) + JUMP_PX
            if cut_here:
                out.append(_run(stroke, s, spot, scale, start, k))
                start = k
                continue
        if cut:
            if start is not None:
                out.append(_run(stroke, s, spot, scale, start, k))
            start = None
        elif start is None:
            start = k
    return out


def _run(stroke, s, spot, scale, i, j) -> dict:
    pts = [[round(float(spot[q, 0]), 2), round(float(spot[q, 1]), 2), round(float(s[q, 2]), 4)] for q in range(i, j)]
    if len(pts) == 1:                                    # a click: one dab
        pts.append([pts[0][0] + 0.01, *pts[0][1:]])
    size = max(0.5, float(stroke["size"]) * float(np.median(scale[i:j])))
    return {"points": pts, "size": round(size, 3), "screen": s[i:j, :2]}


def lay(stroke: dict, pic, item_id: str, size: int) -> list[dict]:
    """One view stroke → the kit's strokes on `item_id`'s canvas (one per run), its view fields left out; the first
    keeps the stroke's id. [] when the camera sees none of the path on the item."""
    base = {k: v for k, v in stroke.items() if not k.startswith("view")}
    return [{**base, "id": stroke["id"] if k == 0 else f'{stroke["id"]}.{k}', "size": r["size"], "points": r["points"]}
            for k, r in enumerate(runs(stroke, pic, item_id, size))]


def laid(canvas: dict, pics: dict, size: int) -> dict:
    """The canvas (paints, paintmasks) with every view stroke laid: what the kit draws. `pics`: texel request JSON
    (texel_key) -> texels.Picture."""
    paints = []
    for layer in canvas.get("paints", []):
        strokes = []
        for s in layer.get("strokes", []):
            v = view_of(s)
            if v is not None:
                strokes += lay(s, pics[texel_key(req_of(v))], canvas["id"], size)
            else:
                strokes.append(s)
        paints.append({**layer, "strokes": strokes})
    return {**canvas, "paints": paints}


def texel_key(req: dict) -> str:
    import json
    return json.dumps(req, sort_keys=True)


def requests(item: dict) -> list[dict]:
    """The texel requests an item's canvas needs: one per distinct stroke view and projection."""
    size = item.get("paintSize", 2048)
    out = {}
    for layer in item.get("paints", []):
        if (p := projected_of(layer)) is not None:
            r = project_req(p, size)
            out[texel_key(r)] = r
        for s in layer.get("strokes", []):
            if (v := view_of(s)) is not None:
                r = req_of(v)
                out[texel_key(r)] = r
    return list(out.values())


# --- projecting a picture

def splat(pic, item_id: str, rgba: np.ndarray, size: int, key: str = "") -> np.ndarray:
    """(size, size, 4) float32 straight RGBA 0..1: the picture `rgba` (float, any size: laid over the texel picture's
    frame) given to each texel the camera sees on `item_id`, averaged; holes up to HOLES texels across filled. Kept by
    `key` (the caller's: texel picture + picture file) when given."""
    if key:
        with _LOCK:
            if key in _SPLATS:
                _SPLATS.move_to_end(key)
                return _SPLATS[key]
    h, w = pic.item.shape
    if rgba.shape[:2] != (h, w):
        from PIL import Image
        rgba = np.asarray(Image.fromarray((np.clip(rgba, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA")
                          .resize((w, h), Image.BILINEAR), np.float32) / 255
    cpx = _canvas(pic, size)
    on = (pic.item == _index(pic, item_id)) & np.isfinite(cpx[..., 0])
    tx = np.clip(cpx[..., 0][on].astype(int), 0, size - 1)
    ty = np.clip(cpx[..., 1][on].astype(int), 0, size - 1)
    flat = ty * size + tx
    src = rgba[on].astype(np.float64)
    src[:, :3] *= src[:, 3:]                             # averaged premultiplied
    acc = np.zeros((size * size, 4))
    np.add.at(acc, flat, src)
    count = np.bincount(flat, minlength=size * size).astype(np.float64)
    acc, count = acc.reshape(size, size, 4), count.reshape(size, size)
    out = _fill(acc, count)
    a = out[..., 3:]
    out[..., :3] = np.where(a > 1e-6, out[..., :3] / np.maximum(a, 1e-6), 0)
    out = out.astype(np.float32)
    if key:
        with _LOCK:
            _SPLATS[key] = out
            while len(_SPLATS) > 4:
                _SPLATS.popitem(last=False)
    return out


def _fill(acc: np.ndarray, count: np.ndarray) -> np.ndarray:
    """Averaged texels; an empty texel with filled ones on at least 2 of its 8 sides takes their mean, HOLES times."""
    have = count > 0
    val = np.where(have[..., None], acc / np.maximum(count, 1)[..., None], 0.0)
    for _ in range(HOLES):
        s = np.zeros_like(val)
        n = np.zeros(have.shape)
        p = np.pad(val, ((1, 1), (1, 1), (0, 0)))
        ph = np.pad(have, 1)
        H, W = have.shape
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                if dx == dy == 1:
                    continue
                m = ph[dy:dy + H, dx:dx + W]
                s += p[dy:dy + H, dx:dx + W] * m[..., None]
                n += m
        grow = ~have & (n >= 2)
        if not grow.any():
            break
        val[grow] = s[grow] / n[grow][:, None]
        have = have | grow
    return val


# --- where view strokes landed

def landed_on(item: dict, pic_of) -> list[dict]:
    """Each view stroke of `item`: {stroke, item, layer, runs, canvasPx, offPx, share}. `pic_of(req)` -> its texel
    picture. canvasPx: per run, its laid path in canvas px (at most 32 points); offPx {mean, max}: how far, in screen
    px, each laid point is seen (re-looked through the same texel picture: the nearest pixel showing that texel) from
    the drawn sample it came from; share: the part of the drawn path that is on this item."""
    size = item.get("paintSize", 2048)
    out = []
    for layer in item.get("paints", []):
        for s in layer.get("strokes", []):
            v = view_of(s)
            if v is None:
                continue
            pic = pic_of(req_of(v))
            rs = runs(s, pic, item["id"], size)
            total = max(1, len(_samples(v["points"])))
            off = _off(pic, item["id"], size, rs)
            out.append({"stroke": s["id"], "item": item["id"], "layer": layer["id"], "runs": len(rs),
                        "canvasPx": [_thin([p[:2] for p in r["points"]]) for r in rs],
                        "offPx": off, "share": round(sum(len(r["screen"]) for r in rs) / total, 3)})
    return out


def _thin(pts: list, most: int = 32) -> list:
    if len(pts) <= most:
        return pts
    pick = np.linspace(0, len(pts) - 1, most).round().astype(int)
    return [pts[i] for i in pick]


def _off(pic, item_id: str, size: int, rs: list) -> dict:
    if not rs:
        return {"mean": None, "max": None}
    from scipy.spatial import cKDTree
    cpx = _canvas(pic, size)
    on = (pic.item == _index(pic, item_id)) & np.isfinite(cpx[..., 0])
    ys, xs = np.nonzero(on)
    tree = cKDTree(cpx[ys, xs])
    d = []
    for r in rs:
        _, at = tree.query(np.asarray([p[:2] for p in r["points"]][:len(r["screen"])]), 1)
        seen = np.stack([xs[at] + 0.5, ys[at] + 0.5], axis=1)
        d.append(np.linalg.norm(seen - r["screen"], axis=1))
    d = np.concatenate(d)
    return {"mean": round(float(d.mean()), 2), "max": round(float(d.max()), 2)}


def landed(scene: dict, data: dict, texels_fn, items=None) -> list[dict]:
    """`landed_on` for every view stroke of the document's canvases (or only `items`), texel pictures through
    texels.cached(scene, req, texels_fn)."""
    from . import paint_scene, texels
    geo = paint_scene.geometry_scene(scene)
    out = []
    for it in paint_scene.canvases(data.get("items", [])):
        if items is None or it["id"] in items:
            out += landed_on(it, lambda req: texels.cached(geo, req, texels_fn))
    return out
