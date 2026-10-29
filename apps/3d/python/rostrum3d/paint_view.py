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

`landed` reports where each view stroke's paint shows through its camera (landed_on) for agents.
"""
from __future__ import annotations

import threading
from collections import OrderedDict

import numpy as np

from .stamp_turn import angle_of

VIEW_KEYS = ("eye", "target", "fov", "frame", "width", "height")
JUMP, JUMP_PX = 3.0, 4.0           # a seam: a canvas step over JUMP × (screen step × scale) + JUMP_PX
HOLES = 1                          # projection: then fill holes up to this many texels across
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
    return spot, hit, _scale(cpx, on, nx, ny), _jacobian(cpx, on, nx, ny)


def _jacobian(cpx: np.ndarray, on: np.ndarray, ix: np.ndarray, iy: np.ndarray) -> np.ndarray:
    """(n, 2, 2): how the canvas spot moves per screen px right (column 0) and down (column 1) at pixels (ix, iy), from
    the neighbours on the same item and piece (no seam: under 64 canvas px; both sides averaged); NaN with none."""
    h, w = on.shape
    cols = []
    for dx, dy in ((1, 0), (0, 1)):
        tot, n = np.zeros((len(ix), 2)), np.zeros(len(ix))
        for sgn in (1, -1):
            x2, y2 = np.clip(ix + sgn * dx, 0, w - 1), np.clip(iy + sgn * dy, 0, h - 1)
            d = (cpx[y2, x2] - cpx[iy, ix]) * sgn
            ok = on[y2, x2] & ((x2 != ix) | (y2 != iy)) & np.isfinite(d).all(axis=1) & (np.linalg.norm(np.nan_to_num(d, nan=1e9), axis=1) < 64)
            tot += np.where(ok[:, None], np.nan_to_num(d), 0.0)
            n += ok
        cols.append(np.where(n[:, None] > 0, tot / np.maximum(n, 1)[:, None], np.nan))
    return np.stack(cols, axis=2)


def _across(jac: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Canvas px per screen px **across** the path at each sample: a band of half-width r round the drawn line is a
    band of half-width r × |det J| / |J d| round its canvas path (d: the path's screen direction). On a surface seen at
    a slant the canvas stretches one way more than the other; sizing the brush by this keeps the painted line as wide
    on the screen as drawn instead of smearing sideways. NaN where unknown."""
    d = np.gradient(s[:, :2], axis=0) if len(s) > 1 else np.array([[1.0, 0.0]])
    d = d / np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
    along = np.linalg.norm(np.einsum("nij,nj->ni", jac, d), axis=1)
    det = np.abs(jac[:, 0, 0] * jac[:, 1, 1] - jac[:, 0, 1] * jac[:, 1, 0])
    return np.where(along > 1e-6, det / np.maximum(along, 1e-6), np.nan)


def runs(stroke: dict, pic, item_id: str, size: int) -> list[dict]:
    """The stroke's runs on `item_id`: [{"points": [[x, y, pressure], …] canvas px, "size": canvas px, "screen":
    the samples' screen px (n×2)}], split where the path leaves the item or jumps a seam."""
    idx = _index(pic, item_id)
    if idx < 0:
        return []
    s = _samples(view_of(stroke)["points"])
    if not len(s):
        return []
    spot, hit, scale, jac = _look(pic, idx, size, s)
    fallback = np.nanmedian(scale[hit]) if np.isfinite(scale[hit]).any() else 1.0
    scale = np.where(np.isfinite(scale), scale, fallback)
    across = _across(jac, s)
    across = np.where(np.isfinite(across) & (across > 0), across, scale)
    out, start = [], None
    for k in range(len(s) + 1):
        cut = k == len(s) or not hit[k]
        if not cut and start is not None and k > start:
            screen = np.linalg.norm(s[k, :2] - s[k - 1, :2])
            cut_here = np.linalg.norm(spot[k] - spot[k - 1]) > JUMP * screen * max(scale[k], scale[k - 1]) + JUMP_PX
            if cut_here:
                out.append(_run(stroke, s, spot, across, start, k, jac))
                start = k
                continue
        if cut:
            if start is not None:
                out.append(_run(stroke, s, spot, across, start, k, jac))
            start = None
        elif start is None:
            start = k
    return out


def _run(stroke, s, spot, across, i, j, jac) -> dict:
    pts = [[round(float(spot[q, 0]), 2), round(float(spot[q, 1]), 2), round(float(s[q, 2]), 4)] for q in range(i, j)]
    if len(pts) == 1:                                    # a click: one dab
        pts.append([pts[0][0] + 0.01, *pts[0][1:]])
    size = max(0.5, float(stroke["size"]) * float(np.median(across[i:j])))
    # the screen's up at the run's start, in canvas px (a stamp stands its picture along it: stamp_turn.py)
    return {"points": pts, "size": round(size, 3), "screen": s[i:j, :2], "up": -jac[i, :, 1]}


def lay(stroke: dict, pic, item_id: str, size: int) -> list[dict]:
    """One view stroke → the kit's strokes on `item_id`'s canvas (one per run), its view fields left out; the first
    keeps the stroke's id. [] when the camera sees none of the path on the item. A stamp (`stampTurn`) stands upright
    as the screen saw it: its angle from the screen's up there (stamp_turn.angle_of)."""
    base = {k: v for k, v in stroke.items() if not k.startswith("view")}
    turn = stroke.get("stampTurn")
    return [{**base, "id": stroke["id"] if k == 0 else f'{stroke["id"]}.{k}', "size": r["size"], "points": r["points"],
             **({"angle": angle_of(r["up"], turn)} if turn is not None else {})}
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
    frame) given to every texel the camera sees on `item_id`. Each square of four neighbouring pixels that shows one
    piece of the item (all four on it, no seam: `_quads`) is filled with samples between them, as many as its texels
    across (a wall seen at a steep angle: many along it), so the picture is solid wherever the surface is seen; a square
    with a pixel of something else in it (the edge of what hides it) is not, so nothing lands behind it. Texels of a
    piece's edge no square reaches take their pixel's colour; holes up to HOLES texels across are filled. Kept by `key`
    (the caller's: texel picture + picture file) when given."""
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
    pre = rgba.astype(np.float32).copy()
    pre[..., :3] *= pre[..., 3:]                          # averaged premultiplied
    cpx = _canvas(pic, size).astype(np.float32)
    on = (pic.item == _index(pic, item_id)) & np.isfinite(cpx[..., 0])
    flats, colss = [], []

    def put(pts, cols):                                    # gathered, then counted once (a whole-canvas count each
        tx = np.clip(pts[:, 0].astype(np.int32), 0, size - 1)          # time cost seconds)
        ty = np.clip(pts[:, 1].astype(np.int32), 0, size - 1)
        flats.append(ty * size + tx)
        colss.append(cols.astype(np.float32))
    put(cpx[on], pre[on])                                  # every seen pixel, its own texel
    for kx, ky, ys, xs in _quads(cpx, on, size):           # and the texels between seen pixels
        fx, fy = np.meshgrid((np.arange(kx, dtype=np.float32) + 0.5) / kx, (np.arange(ky, dtype=np.float32) + 0.5) / ky)
        fx, fy = fx.ravel()[None, :, None], fy.ravel()[None, :, None]
        w00, w10, w01, w11 = (1 - fx) * (1 - fy), fx * (1 - fy), (1 - fx) * fy, fx * fy
        step = max(1, 200000 // (kx * ky))                  # bounded memory: ~200 000 samples at a time
        for i in range(0, len(ys), step):
            y, x = ys[i:i + step], xs[i:i + step]
            corners = [(y, x), (y, x + 1), (y + 1, x), (y + 1, x + 1)]
            pts = sum(wt * cpx[cy, cx][:, None, :] for wt, (cy, cx) in zip((w00, w10, w01, w11), corners))
            cols = sum(wt * pre[cy, cx][:, None, :] for wt, (cy, cx) in zip((w00, w10, w01, w11), corners))
            put(pts.reshape(-1, 2), cols.reshape(-1, 4))
    flat, cols = np.concatenate(flats), np.concatenate(colss)
    acc = np.stack([np.bincount(flat, cols[:, c], size * size) for c in range(4)], -1)
    count = np.bincount(flat, minlength=size * size)
    out = _fill(acc.reshape(size, size, 4), count.reshape(size, size))
    a = out[..., 3:]
    out[..., :3] = np.where(a > 1e-6, out[..., :3] / np.maximum(a, 1e-6), 0)
    out = out.astype(np.float32)
    if key:
        with _LOCK:
            _SPLATS[key] = out
            while len(_SPLATS) > 4:
                _SPLATS.popitem(last=False)
    return out


MOST_ACROSS = 24                    # a pixel square is filled with at most this many samples each way


def _quads(cpx: np.ndarray, on: np.ndarray, size: int):
    """The squares of four seen pixels on one piece: (kx, ky, ys, xs) groups, kx × ky the samples each needs (its
    canvas steps right and down, rounded up). A square is one piece when its four corners lie as on a flat patch (the
    far corner within half the steps of where the two near steps put it) and no step is a seam's jump."""
    q = on[:-1, :-1] & on[:-1, 1:] & on[1:, :-1] & on[1:, 1:]
    c00, c10, c01, c11 = cpx[:-1, :-1], cpx[:-1, 1:], cpx[1:, :-1], cpx[1:, 1:]
    dx, dy = np.nan_to_num(c10 - c00), np.nan_to_num(c01 - c00)
    lx, ly = np.linalg.norm(dx, axis=-1), np.linalg.norm(dy, axis=-1)
    flat = np.linalg.norm(np.nan_to_num(c11 - c00) - dx - dy, axis=-1) <= 0.5 * (lx + ly) + 2
    q &= flat & (lx < max(16.0, size / 16)) & (ly < max(16.0, size / 16)) & ((lx > 1) | (ly > 1))
    kx = np.clip(np.ceil(np.maximum(lx, np.linalg.norm(np.nan_to_num(c11 - c01), axis=-1))), 1, MOST_ACROSS)
    ky = np.clip(np.ceil(np.maximum(ly, np.linalg.norm(np.nan_to_num(c11 - c10), axis=-1))), 1, MOST_ACROSS)
    ys, xs = np.nonzero(q)
    if not len(ys):
        return
    key = (kx[ys, xs].astype(int) * 100 + ky[ys, xs].astype(int))
    order = np.argsort(key, kind="stable")
    key, ys, xs = key[order], ys[order], xs[order]
    bounds = np.flatnonzero(np.diff(key)) + 1
    for a, b in zip([0, *bounds], [*bounds, len(key)]):
        yield int(key[a] // 100), int(key[a] % 100), ys[a:b], xs[a:b]


def _fill(acc: np.ndarray, count: np.ndarray) -> np.ndarray:
    """Averaged texels; an empty texel with filled ones on at least 2 of its 4 sides takes their mean, HOLES times."""
    have = count > 0
    val = np.where(have[..., None], acc / np.maximum(count, 1)[..., None], 0.0).astype(np.float32)
    H, W = have.shape
    for _ in range(HOLES):
        p, ph = np.pad(val, ((1, 1), (1, 1), (0, 0))), np.pad(have, 1)
        s, n = np.zeros_like(val), np.zeros(have.shape, np.float32)
        for dy, dx in ((0, 1), (2, 1), (1, 0), (1, 2)):
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

OFF_OK, OFF_SHARE = 3.0, 0.25     # landed: no paint seen further outside the brush than max(OFF_OK, OFF_SHARE × radius)
COVER_OK = 0.8                    # … the paint covers at least this share of the line's band on the item
MORE_PIECES = 2                   # … and comes in at most this many more pieces than the band itself has


def landed_on(item: dict, pic_of) -> list[dict]:
    """Each view stroke of `item`, measured by where its paint **shows** through its own camera: {stroke, item, layer,
    runs, canvasPx, share, seenPx, pieces, wantPieces, covered, offPx {median, max}, landed, verdict}. `pic_of(req)` ->
    its texel picture.

    The laid runs (canvas paths with their brush size) are turned back into the picture: a pixel showing the item is
    painted when the texel it shows lies within the brush of a run (so paint the camera sees somewhere else, through
    a stretched or shared part of the canvas, counts too). offPx: how far painted pixels lie outside the drawn line's
    band (the brush's half-width round the path, screen px; 0 = all inside), median and max; pieces: the painted
    pixels' separate patches (wantPieces: the band's own on this item); covered: the share of the band painted; share:
    the part of the drawn path on this item; canvasPx: per run, its laid path (at most 32 points). `landed` follows
    those numbers (OFF_OK, OFF_SHARE, COVER_OK, MORE_PIECES); `verdict` says them in words."""
    size = item.get("paintSize", 2048)
    out = []
    for layer in item.get("paints", []):
        for s in layer.get("strokes", []):
            v = view_of(s)
            if v is None:
                continue
            pic = pic_of(req_of(v))
            rs = runs(s, pic, item["id"], size)
            samples = _samples(v["points"])
            seen = _seen(pic, item["id"], size, rs, samples, float(s["size"]) / 2)
            row = {"stroke": s["id"], "item": item["id"], "layer": layer["id"], "runs": len(rs),
                   "canvasPx": [_thin([p[:2] for p in r["points"]]) for r in rs],
                   "share": round(sum(len(r["screen"]) for r in rs) / max(1, len(samples)), 3), **seen}
            row["landed"], row["verdict"] = verdict(row, float(s["size"]) / 2)
            out.append(row)
    return out


def verdict(row: dict, radius: float) -> tuple[bool, str]:
    """(landed, words) from a landed_on row's own numbers; never one without the other."""
    if not row["runs"] or not row["seenPx"]:
        return False, f'laid no paint: {row["item"]} is not under its path from that view'
    tol = max(OFF_OK, OFF_SHARE * radius)
    wrong = []
    if row["offPx"]["max"] > tol:
        wrong.append(f'up to {row["offPx"]["max"]:.0f} screen px outside the line')
    if row["pieces"] > row["wantPieces"] + MORE_PIECES:
        wrong.insert(0, f'in {row["pieces"]} pieces')
    if row["covered"] < COVER_OK:
        wrong.append(f'covering {row["covered"] * 100:.0f} % of the line')
    if not wrong:
        return True, "landed"
    return False, f'painted {", ".join(wrong)} on {row["item"]} (seen through its camera)'


def _thin(pts: list, most: int = 32) -> list:
    if len(pts) <= most:
        return pts
    pick = np.linspace(0, len(pts) - 1, most).round().astype(int)
    return [pts[i] for i in pick]


def _dense(pts: np.ndarray, step: float) -> np.ndarray:
    """A polyline resampled at most `step` apart (its own points kept)."""
    if len(pts) < 2:
        return pts
    out = [pts[:1]]
    for a, b in zip(pts[:-1], pts[1:]):
        n = int(min(4096, max(1, np.ceil(np.linalg.norm(b - a) / step))))
        out.append(a + (b - a) * (np.arange(1, n + 1) / n)[:, None])
    return np.concatenate(out)


def _seen(pic, item_id: str, size: int, rs: list, samples: np.ndarray, radius: float) -> dict:
    """Where the laid runs show through `pic` (landed_on's seenPx, pieces, wantPieces, covered, offPx)."""
    from scipy import ndimage
    from scipy.spatial import cKDTree
    cpx = _canvas(pic, size)
    on = (pic.item == _index(pic, item_id)) & np.isfinite(cpx[..., 0])
    ys, xs = np.nonzero(on)
    painted = np.zeros(len(ys), bool)
    if len(ys) and rs:
        texel = cpx[ys, xs]
        for r in rs:
            path = np.asarray([p[:2] for p in r["points"]], np.float64)
            half = float(r["size"]) / 2
            tree = cKDTree(_dense(path, max(0.5, half / 4)))
            d, _ = tree.query(texel, 1, distance_upper_bound=half + 1)
            painted |= d <= half
    if len(ys) and len(samples):
        line = cKDTree(_dense(samples[:, :2], 0.5))
        dist, _ = line.query(np.stack([xs + 0.5, ys + 0.5], axis=1), 1)
    else:
        dist = np.full(len(ys), np.inf)
    band = dist <= radius
    out = np.maximum(dist[painted] - radius, 0.0)

    def patches(mask):
        img = np.zeros(on.shape, bool)
        img[ys[mask], xs[mask]] = True
        return int(ndimage.label(img, np.ones((3, 3), bool))[1])
    return {"seenPx": int(painted.sum()), "pieces": patches(painted), "wantPieces": patches(band),
            "covered": round(float((painted & band).sum() / max(1, band.sum())), 3),
            "offPx": {"median": round(float(np.median(out)), 2) if len(out) else None,
                      "max": round(float(out.max()), 2) if len(out) else None}}


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
