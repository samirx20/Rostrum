"""G-buffer: rasterize the still life from the shot camera, per pixel which object, material,
triangle, barycentrics, UV, world position, normal and depth. numpy only, seconds.

  python gbuffer.py [--width 1920] [--crop X Y W H]     # builds (or reuses) the cache, prints stats

Cache: $ROSTRUM_MODEL_CACHE or proofs/paint/model/.cache, keyed by the scene source + size.
`fragments()` is the one triangle rasterizer, also used in UV space by project.py / coverage.py.
"""
import argparse, hashlib, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene  # noqa: E402

CACHE = os.environ.get("ROSTRUM_MODEL_CACHE") or os.path.join(scene.HERE, ".cache")
MAX_CAND = 4_000_000          # candidate pixels per batch (memory bound)


def fragments(v, W, H, clip=True):
    """Yield (tri, px, py, l) for every pixel centre inside each 2D triangle v (T,3,2).
    l (n,3) are affine barycentrics. clip=False keeps pixels outside 0..W/H (caller wraps)."""
    lo, hi = v.min(1), v.max(1)
    x0, y0 = np.ceil(lo[:, 0] - 0.5).astype(np.int64), np.ceil(lo[:, 1] - 0.5).astype(np.int64)
    x1, y1 = np.floor(hi[:, 0] - 0.5).astype(np.int64), np.floor(hi[:, 1] - 0.5).astype(np.int64)
    if clip:
        x0, y0 = np.maximum(x0, 0), np.maximum(y0, 0)
        x1, y1 = np.minimum(x1, W - 1), np.minimum(y1, H - 1)
    a, b, c = v[:, 0], v[:, 1], v[:, 2]
    area = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
    ok = (x1 >= x0) & (y1 >= y0) & (np.abs(area) > 1e-12)
    bw = np.where(ok, x1 - x0 + 1, 0); bh = np.where(ok, y1 - y0 + 1, 0)
    kw = 1 << np.ceil(np.log2(np.maximum(bw, 1))).astype(np.int64)
    kh = 1 << np.ceil(np.log2(np.maximum(bh, 1))).astype(np.int64)
    for gw, gh in sorted(set(zip(kw[ok].tolist(), kh[ok].tolist()))):
        ids = np.nonzero(ok & (kw == gw) & (kh == gh))[0]
        oy, ox = np.divmod(np.arange(gw * gh), gw)
        step = max(1, MAX_CAND // (gw * gh))
        for s in range(0, len(ids), step):
            t = ids[s:s + step]
            px = x0[t, None] + ox[None]; py = y0[t, None] + oy[None]
            inb = (px <= x1[t, None]) & (py <= y1[t, None])
            qx, qy = px + 0.5, py + 0.5
            A, B, C, ar = a[t], b[t], c[t], area[t, None]
            l0 = ((B[:, None, 0] - qx) * (C[:, None, 1] - qy) - (B[:, None, 1] - qy) * (C[:, None, 0] - qx)) / ar
            l1 = ((C[:, None, 0] - qx) * (A[:, None, 1] - qy) - (C[:, None, 1] - qy) * (A[:, None, 0] - qx)) / ar
            l2 = 1.0 - l0 - l1
            m = inb & (l0 >= -1e-7) & (l1 >= -1e-7) & (l2 >= -1e-7)
            if m.any():
                ti = np.broadcast_to(t[:, None], m.shape)[m]
                yield ti, px[m], py[m], np.stack([l0[m], l1[m], l2[m]], -1)


def perspective(l, zc):
    """Affine screen barycentrics + vertex camera depths -> perspective-correct ones, depth."""
    w = l / zc
    s = w.sum(-1, keepdims=True)
    return w / s, 1.0 / s[..., 0]


def build(sc, cam):
    """Rasterize: returns dict obj (H,W int16, -1 = nothing), tri (int32), bary (H,W,3), zc."""
    x, y, zc = cam.to_frame(sc["P"])
    bx, by = cam.frame_to_buf(x, y)
    front = (zc > 1.0).all(1)                       # no triangle crosses the camera plane here
    keep = np.nonzero(front)[0]
    v = np.stack([bx, by], -1)[keep]
    W, H = cam.W, cam.H
    zbuf = np.full(W * H, np.inf); tbuf = np.full(W * H, -1, np.int64); lbuf = np.zeros((W * H, 3))
    for ti, px, py, l in fragments(v, W, H):
        t = keep[ti]
        b, z = perspective(l, zc[t])
        pix = py * W + px
        o = np.lexsort((z, pix))                    # nearest fragment per pixel within the batch
        pix, z, t, l = pix[o], z[o], t[o], l[o]
        first = np.r_[True, pix[1:] != pix[:-1]]
        pix, z, t, l = pix[first], z[first], t[first], l[first]
        win = z < zbuf[pix]
        zbuf[pix[win]] = z[win]; tbuf[pix[win]] = t[win]; lbuf[pix[win]] = l[win]
    hit = tbuf >= 0
    bary = np.zeros((W * H, 3), np.float32)
    if hit.any():
        bary[hit] = perspective(lbuf[hit], zc[tbuf[hit]])[0]
    obj = np.where(hit, sc["tri_obj"][np.maximum(tbuf, 0)], -1).astype(np.int16)
    return dict(obj=obj.reshape(H, W), tri=tbuf.astype(np.int32).reshape(H, W),
                bary=bary.reshape(H, W, 3), zc=np.where(hit, zbuf, np.inf).astype(np.float32).reshape(H, W))


def _key(cam):
    h = hashlib.sha1()
    for f in ("make_scene.py", "geo.py"):
        with open(os.path.join(scene.SCENE_DIR, f), "rb") as fh:
            h.update(fh.read())
    with open(os.path.abspath(__file__), "rb") as fh:
        h.update(fh.read())
    h.update(repr((cam.W, cam.H, cam.crop)).encode())
    return h.hexdigest()[:16]


class GBuffer:
    """Loaded G-buffer with derived per-pixel attributes (computed on demand from tri + bary)."""

    def __init__(self, width=scene.FRAME_W, crop=None, height=None, sc=None):
        self.sc = sc or scene.load()
        self.cam = scene.Camera(width, height, crop)
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, f"gbuf-{self.cam.W}x{self.cam.H}-{_key(self.cam)}.npz")
        if os.path.exists(path):
            d = dict(np.load(path))
        else:
            d = build(self.sc, self.cam)
            np.savez(path, **d)
        self.path = path
        self.obj, self.tri, self.bary, self.zc = d["obj"], d["tri"], d["bary"], d["zc"]
        self.hit = self.obj >= 0
        self.mat = np.where(self.hit, self.sc["obj_material"][np.maximum(self.obj, 0)], -1)

    def _interp(self, key):
        t = np.maximum(self.tri, 0)
        return np.einsum("hwk,hwkc->hwc", self.bary, self.sc[key][t]) * self.hit[..., None]

    @property
    def uv(self): return self._interp("UV")

    @property
    def pos(self): return self._interp("P")

    @property
    def normal(self):
        n = self._interp("N")
        return n / np.maximum(np.linalg.norm(n, axis=-1, keepdims=True), 1e-12)

    def objects_of(self, material):
        mi = scene.material_index(self.sc, material)
        return [o for o, m in zip(self.sc["objects"], self.sc["obj_material"]) if m == mi]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--width", type=int, default=scene.FRAME_W)
    ap.add_argument("--crop", type=float, nargs=4, metavar=("X", "Y", "W", "H"))
    a = ap.parse_args()
    t = time.time()
    g = GBuffer(a.width, a.crop)
    print(f"G-buffer {g.cam.W}x{g.cam.H} crop={g.cam.crop} in {time.time() - t:.2f}s -> {g.path}")
    print(f"triangles {len(g.sc['tri_obj'])}, pixels covered {g.hit.mean() * 100:.1f}%")
    for i, n in enumerate(g.sc["objects"]):
        print(f"  {n:15s} {g.sc['materials'][g.sc['obj_material'][i]]:10s} {(g.obj == i).sum():8d} px")


if __name__ == "__main__":
    main()
