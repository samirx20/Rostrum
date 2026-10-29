"""Automatic masks (SPEC §13, Substance-style): greyscale pictures of a surface's own shape, laid on its unfolded
paint picture, that a paint layer's coverage is multiplied by (paint_fields.LAYER `mask`): wear only where edges are,
dust only on top. They are tools: what is worn or dusty is the person's or agent's layer.

- **Edges** / **Cavities**: how much the surface bends outward (a convex edge, a corner, a ridge) or inward (a crease,
  a hollow) within REACH of the item's size round each spot: the signed bend of the surface's directions there
  (Σ k·(n_q − n_p)·(q − p) / Σ k·|q − p|², ≈ 1 / radius on a ball), × REACH: 1 where it turns as sharply as a ball of
  that reach, more on a sharp edge.
- **Facing up**: how straight up the surface faces (its normal's +Y, the item's own up).
- **Thin parts**: how thin the item is behind each spot: a short ray inward meets the other side within THIN of its
  size (1 = paper thin, 0 = at least that thick).

Made once per surface shape and paint size into the shared cache (`masks`): a clay from its unfolded surface
(clay_paint), a mesh from its built mesh as kept when it was unfolded (`keep_geometry`, the same corners as `uvs`).
Numpy and a k-d tree on a cloud of points spread over the surface; a 2048 picture of a typical clay takes seconds.
"""
from __future__ import annotations

import hashlib
import json
import threading
from collections import OrderedDict

import numpy as np
from rostrum_core.cache import CACHE, cache_key

from .uv_raster import Geo, raster

VERSION = "rostrum3d-paintmasks@2"
NAMES = ("edges", "cavities", "up", "thin")
REACH, THIN = 0.04, 0.12            # shares of the item's size (its bounding box's diagonal)
MOST = 120_000                      # points in the cloud at most
WORK = 1024                         # masks are worked out at most this big, then scaled up (they change slowly)
GROW = 3                            # and first grown this many texels past each piece (no dark rim when scaled)
_LOCK = threading.RLock()
_HELD: OrderedDict = OrderedDict()  # cache key -> {name: uint8 array}, the last few


def keep_geometry(uvs, geometry: dict) -> None:
    """Keep a mesh's built mesh (the engine's `geometry`) beside its unfolding, keyed by the `uvs` it was unfolded to
    (xatlas's corners for exactly that mesh; the masks are keyed by the kept mesh's own content)."""
    data = {k: list(geometry[k]) for k in ("points", "faceCounts", "faceIndices")}
    CACHE.put("meshgeo", _geo_key(uvs), lambda d: (d / "geometry.json").write_text(json.dumps(data)), {"what": "mesh"})


def _geo_key(uvs) -> str:
    return cache_key("mesh.geometry", VERSION, [hashlib.sha1(np.asarray(uvs, np.float32).tobytes()).hexdigest()], {})


def geo_of(item: dict, surface) -> tuple[Geo, str]:
    """(the surface, what it is: its cache name) of a painted clay (`surface`) or a mesh. Loud for a mesh whose built
    mesh wasn't kept (unfolded before masks existed)."""
    if surface is not None:
        return Geo.of_surface(surface), f"clay:{surface.key}"
    key = _geo_key(item.get("uvs") or [])
    f = CACHE.get("meshgeo", key) if item.get("uvs") else None
    if f is None:
        raise ValueError(f'mesh {item["id"]}: its shape for the automatic masks is not known: unfold it again '
                         "(mesh.unfold) and the masks follow")
    raw = (f / "geometry.json").read_bytes()
    return Geo.of_mesh(json.loads(raw), item["uvs"]), f"mesh:{hashlib.sha1(raw).hexdigest()}"


def masks(item: dict, surface, size: int) -> tuple[str, dict[str, np.ndarray]]:
    """(their cache key, {name: size × size uint8}) of the item's surface, made once (kept in the shared cache and
    here)."""
    geo, key = _key(item, surface, size)
    with _LOCK:
        if key in _HELD:
            _HELD.move_to_end(key)
            return key, _HELD[key]
    from PIL import Image
    entry = CACHE.get("paintmask", key) or CACHE.put("paintmask", key, lambda d: [
        Image.fromarray(m, "L").save(d / f"{n}.png", compress_level=1) for n, m in compute(geo, size).items()],
        {"item": item["id"], "size": size})
    out = {n: np.asarray(Image.open(entry / f"{n}.png")) for n in NAMES}
    with _LOCK:
        _HELD[key] = out
        while len(_HELD) > 4:
            _HELD.popitem(last=False)
    return key, out


def _key(item: dict, surface, size: int) -> tuple[Geo, str]:
    geo, what = geo_of(item, surface)
    return geo, cache_key("paint.masks", VERSION, [what], {"size": size})


def ready(item: dict, surface, size: int) -> bool:
    """The item's masks are made (no wait for them); False also when its shape isn't known (masks() says why)."""
    try:
        _, key = _key(item, surface, size)
    except ValueError:
        return False
    with _LOCK:
        return key in _HELD or CACHE.get("paintmask", key) is not None


def levels(mask: np.ndarray, spread: float, invert: bool) -> np.ndarray:
    """The mask (uint8) as the layer uses it, 0..1 float32: Spread 0 keeps only its strongest part, 1 reaches as far as
    it goes (a levels step: from (1 − spread) × 0.9 to 0.25 above it); Invert swaps where it is."""
    lo = (1.0 - float(spread)) * 0.9
    m = np.clip((mask.astype(np.float32) / 255 - lo) / 0.25, 0, 1)
    return 1 - m if invert else m


def compute(geo: Geo, size: int) -> dict[str, np.ndarray]:
    """{name: size × size uint8}: worked out at min(size, WORK), grown past the pieces and scaled up."""
    n = min(size, WORK)
    small = _compute(geo, n)
    if n == size:
        return {k: v for k, v in small.items() if k != "_on"}
    from PIL import Image
    grown = _grow(np.stack([small[k] for k in NAMES], -1), small["_on"])
    return {k: np.asarray(Image.fromarray(np.ascontiguousarray(grown[..., i]), "L").resize((size, size), Image.BILINEAR))
            for i, k in enumerate(NAMES)}


def _grow(img: np.ndarray, on: np.ndarray) -> np.ndarray:
    """`img` (h × w × c) with the texels just outside the pieces (GROW rings) set to their inside neighbours' mean."""
    v, have = img.astype(np.float32), on.copy()
    for _ in range(GROW):
        pv, ph = np.pad(v, ((1, 1), (1, 1), (0, 0))), np.pad(have, 1).astype(np.float32)[..., None]
        tot, cnt = np.zeros_like(v), np.zeros(v.shape[:2] + (1,), np.float32)
        for dy, dx in ((0, 1), (2, 1), (1, 0), (1, 2)):
            h = ph[dy:dy + v.shape[0], dx:dx + v.shape[1]]
            tot += pv[dy:dy + v.shape[0], dx:dx + v.shape[1]] * h
            cnt += h
        new = ~have & (cnt[..., 0] > 0)
        v[new] = tot[new] / cnt[new]
        have |= new
    return np.round(v).astype(np.uint8)


def _compute(geo: Geo, size: int) -> dict[str, np.ndarray]:
    tri, bary = raster(geo, size)
    on = tri >= 0
    corners = geo.points[geo.tris]                                      # m × 3 × 3
    fn = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    area = np.linalg.norm(fn, axis=1) / 2
    fn = fn / np.maximum(2 * area, 1e-30)[:, None]
    diag = float(np.linalg.norm(geo.points.max(0) - geo.points.min(0))) or 1.0
    reach, thin = REACH * diag, THIN * diag
    cloud, normal = _cloud(corners, fn, area, reach)
    from scipy.spatial import cKDTree
    tree = cKDTree(cloud)
    bend = _smooth(tree, cloud, _bend(tree, cloud, normal, reach) * reach, reach / 2)
    thick = _thickness(tree, cloud, normal, thin)
    ts, tb = tri[on], bary[on]
    spot = np.einsum("aj,ajk->ak", tb, corners[ts])
    d, near = tree.query(spot, 3, workers=3)
    wt = 1.0 / np.maximum(d, 1e-9)
    wt /= wt.sum(1, keepdims=True)
    at = lambda v: (v[near] * wt).sum(1)  # noqa: E731
    b = at(bend)
    vals = {"edges": np.clip(b, 0, 1), "cavities": np.clip(-b, 0, 1), "up": np.clip(fn[ts][:, 1], 0, 1),
            "thin": np.clip(at(thick), 0, 1)}
    out = {}
    for n, v in vals.items():
        img = np.zeros((size, size), np.uint8)
        img[on] = np.round(v * 255).astype(np.uint8)
        out[n] = img
    out["_on"] = on
    return out


def _cloud(corners, fn, area, reach):
    """Points spread evenly over the surface (about reach / 3 apart, at most MOST), each with its triangle's normal."""
    total = float(area.sum()) or 1.0
    n = int(min(MOST, max(2000, total / (reach / 3) ** 2)))
    rng = np.random.default_rng(7)
    t = rng.choice(len(area), n, p=area / total)
    r1, r2 = np.sqrt(rng.random(n)), rng.random(n)
    w = np.stack([1 - r1, r1 * (1 - r2), r1 * r2], 1)
    return np.einsum("aj,ajk->ak", w, corners[t]), fn[t]


def _bend(tree, cloud, normal, reach) -> np.ndarray:
    """Each point's signed bend within `reach` (≈ 1 / radius; + outward, − inward)."""
    pairs = tree.query_pairs(reach, output_type="ndarray")
    i, j = pairs[:, 0], pairs[:, 1]
    d = cloud[j] - cloud[i]
    dd = (d * d).sum(1)
    k = (1 - dd / reach ** 2) ** 2
    num = k * ((normal[j] - normal[i]) * d).sum(1)                  # symmetric: counts for both ends
    top, bot = np.zeros(len(cloud)), np.zeros(len(cloud))
    np.add.at(top, i, num)
    np.add.at(top, j, num)
    np.add.at(bot, i, k * dd)
    np.add.at(bot, j, k * dd)
    return top / np.maximum(bot, 1e-30)


def _smooth(tree, cloud, v, r) -> np.ndarray:
    """`v` averaged over each point's neighbours within `r` (the cloud's random spread no longer shows as grain)."""
    pairs = tree.query_pairs(r, output_type="ndarray")
    i, j = pairs[:, 0], pairs[:, 1]
    k = (1 - ((cloud[j] - cloud[i]) ** 2).sum(1) / r ** 2) ** 2
    top, bot = v.copy(), np.ones(len(v))
    np.add.at(top, i, k * v[j])
    np.add.at(top, j, k * v[i])
    np.add.at(bot, i, k)
    np.add.at(bot, j, k)
    return top / bot


def _thickness(tree, cloud, normal, thin) -> np.ndarray:
    """1 − (how far a ray inward from each point runs before it meets the other side) / thin; 0 when it doesn't
    within `thin`: the other side is a cloud point near the ray facing the other way."""
    gap = 1.5 * float(np.median(tree.query(cloud[:2000], 2)[0][:, 1]))
    out = np.zeros(len(cloud))
    left = np.ones(len(cloud), bool)
    for s in range(1, 13):
        t = thin * s / 12
        idx = np.nonzero(left)[0]
        if not len(idx):
            break
        d, q = tree.query(cloud[idx] - normal[idx] * t, 1)
        hit = (d < max(gap, thin / 12)) & ((normal[q] * normal[idx]).sum(1) < 0)
        out[idx[hit]] = 1 - t / thin
        left[idx[hit]] = False
    return out
