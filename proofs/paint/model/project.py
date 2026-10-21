"""Paint from the camera: carry a screen-space paint layer onto a material's texture.

  python project.py MATERIAL --png layer.png | --doc d.paint.json --layer NAME
                    [--object NAME ...] [--tex in.png] --out new.png [--grazing 80] [--ss 2]
                    [--opacity 1] [--check view_dir]

The layer is drawn over the 1920x1080 frame (any size with the same 16:9 shape is scaled). Every
texel of the chosen object(s) looks up where it lands in the frame; if the camera sees that very
spot (same object, same depth, turned less than --grazing degrees away) the layer colour there is
laid over the texel. Each texel is sampled --ss x --ss times so strokes don't alias. Shared
materials: --object limits the paint to those objects (default: every object with the material;
note a texel shared by two objects then takes paint from both). Painted edges are grown 2 texels
outward into unused texture space so UV seams don't show a thin line.
--check DIR renders the flat model view before / after and measures where the paint landed.
"""
import argparse, json, os, sys, time
import numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene, tex  # noqa: E402
from gbuffer import GBuffer, fragments  # noqa: E402

KIT = os.path.normpath(os.path.join(scene.HERE, "..", "kit"))


def load_layer(png=None, doc=None, layer=None):
    """-> premultiplied RGBA float32 (H,W,4) over the frame."""
    if png:
        a = tex.load(png, rgba=True).copy()
        a[..., :3] *= a[..., 3:]
        return a
    sys.path.insert(0, KIT)
    from doc import Doc                                   # the 2D kit's document
    d = Doc.open(doc)
    names = [l["name"] for l in d.layers()]
    if layer not in names:
        raise SystemExit(f"{doc} has no layer {layer!r}; layers: {', '.join(names)}")
    return d.layer_pixels(layer)


def uv_samples(sc, tris, size, ss):
    """Sub-texel samples of the triangles in UV space -> (texel flat index, tri, barycentrics)."""
    W, H = size
    uv = sc["UV"][tris]
    v = np.stack([uv[..., 0] * W * ss, (1 - uv[..., 1]) * H * ss], -1)
    out = [(np.mod(py // ss, H) * W + np.mod(px // ss, W), tris[ti], l)
           for ti, px, py, l in fragments(v, W * ss, H * ss, clip=False)]
    if not out:
        return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros((0, 3))
    return tuple(np.concatenate(z) for z in zip(*out))


def island_mask(sc, mat_idx, size):
    """Texels covered by any triangle of the material (for seam growth and coverage)."""
    tris = np.nonzero(sc["obj_material"][sc["tri_obj"]] == mat_idx)[0]
    t, _, _ = uv_samples(sc, tris, size, 1)
    m = np.zeros(size[0] * size[1], bool); m[t] = True
    return m.reshape(size[1], size[0])


def grow(color, alpha, keep_out, steps=2):
    """Spread painted texels `steps` texels into texture space no triangle uses."""
    for _ in range(steps):
        best_a, best_c = alpha.copy(), color.copy()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (-1, 1), (1, -1), (1, 1)]:
            na, nc = np.roll(alpha, (dy, dx), (0, 1)), np.roll(color, (dy, dx), (0, 1))
            take = keep_out & (na > best_a)
            best_a = np.where(take, na, best_a); best_c = np.where(take[..., None], nc, best_c)
        alpha, color = best_a, best_c
    return color, alpha


def visible(g, tri, p, n):
    """Surface samples (triangle, world point, normal) -> frame x, y, seen by the camera, facing
    angle in degrees (0 = straight at the camera). Seen = the G-buffer shows the same object at
    that pixel and the same depth (tolerance grows with the slant, as one pixel spans more depth)."""
    x, y, zc = g.cam.to_frame(p)
    bx, by = g.cam.frame_to_buf(x, y)
    inside = (bx >= 0) & (bx < g.cam.W) & (by >= 0) & (by < g.cam.H)
    j, i = np.clip(by.astype(int), 0, g.cam.H - 1), np.clip(bx.astype(int), 0, g.cam.W - 1)
    to_cam = g.cam.pos - p
    cos = (n * to_cam).sum(1) / np.linalg.norm(to_cam, axis=1)
    ang = np.degrees(np.arccos(np.clip(cos, -1, 1)))
    px_cm = zc / (g.cam.fx * g.cam.scale)
    tol = 0.03 + 1.5 * px_cm * np.tan(np.radians(np.minimum(np.where(ang > 90, 180 - ang, ang), 85)))
    seen = inside & (g.obj[j, i] == g.sc["tri_obj"][tri]) & (np.abs(g.zc[j, i] - zc) < tol)
    return x, y, seen, ang


def project(layer, material, g, objects=None, texture=None, grazing=80.0, ss=2, opacity=1.0):
    """Returns (new texture HxWx3 sRGB, report dict). layer: premultiplied RGBA over the frame."""
    t0 = time.time()
    sc = g.sc
    mi = scene.material_index(sc, material)
    material = sc["materials"][mi]
    if material in ("Blocker",):
        raise SystemExit("Blocker has no texture")
    obj_ids = [scene.object_index(sc, o) for o in objects] if objects else \
        [i for i, m in enumerate(sc["obj_material"]) if m == mi]
    bad = [sc["objects"][o] for o in obj_ids if sc["obj_material"][o] != mi]
    if bad:
        raise SystemExit(f"{bad} do not use material {material}")
    if layer.shape[:2] != (g.cam.H, g.cam.W) or g.cam.crop != (0, 0, scene.FRAME_W, scene.FRAME_H):
        raise SystemExit(f"layer {layer.shape[1]}x{layer.shape[0]} must match a whole-frame G-buffer "
                         f"({g.cam.W}x{g.cam.H}); use the frame's 16:9 shape")
    T = tex.load(texture or scene.texture_path(material))[..., :3].copy()
    H, W = T.shape[:2]
    s = layer.shape[1] / scene.FRAME_W
    tris = np.nonzero(np.isin(sc["tri_obj"], obj_ids))[0]
    ys, xs = np.nonzero(layer[..., 3] > 1 / 255)
    if len(xs):                                           # only triangles under the paint
        fx, fy, _ = g.cam.to_frame(sc["P"][tris])
        tris = tris[(fx.max(1) >= xs.min() / s - 2) & (fx.min(1) <= xs.max() / s + 3)
                    & (fy.max(1) >= ys.min() / s - 2) & (fy.min(1) <= ys.max() / s + 3)]
    else:
        tris = tris[:0]
    tix, tri, l = uv_samples(sc, tris, (W, H), ss)
    p = np.einsum("nk,nkc->nc", l, sc["P"][tri])
    n = np.einsum("nk,nkc->nc", l, sc["N"][tri]); n /= np.linalg.norm(n, axis=1, keepdims=True)
    x, y, seen, ang = visible(g, tri, p, n)
    ok = seen & (ang < grazing)
    rgba = tex.bilinear(layer, x[ok] * s, y[ok] * s) * opacity
    N = W * H
    cnt = np.bincount(tix, minlength=N).astype(np.float64)
    A = np.bincount(tix[ok], rgba[:, 3], N) / np.maximum(cnt, 1)
    C = np.stack([np.bincount(tix[ok], rgba[:, k], N) for k in range(3)], -1) / np.maximum(cnt, 1)[:, None]
    A, C = A.reshape(H, W), C.reshape(H, W, 3)
    C, A = grow(C, A, ~island_mask(sc, mi, (W, H)))
    new = T * (1 - A[..., None]) + C
    # screen side: where did the layer's paint fall?
    la = layer[..., 3]                                   # G-buffer is built at the layer's size
    painted = la > 0.01
    on = np.isin(g.obj, obj_ids)
    face = np.degrees(np.arccos(np.clip(-(g.normal * _view_dirs(g)).sum(-1), -1, 1)))
    others = {}
    for o in np.unique(g.obj[painted & ~on]):
        others["nothing" if o < 0 else sc["objects"][o]] = int((painted & (g.obj == o)).sum())
    rep = dict(material=material, objects=[sc["objects"][o] for o in obj_ids],
               texture=f"{W}x{H}", texels_changed=int((A > 1 / 255).sum()),
               paint_px=int(painted.sum()),
               paint_px_landed=int((painted & on & (face < grazing)).sum()),
               paint_px_grazing_dropped=int((painted & on & (face >= grazing)).sum()),
               paint_px_missed=others, grazing_cutoff_deg=grazing,
               texel_samples_grazing_dropped=int((seen & (ang >= grazing) & (ang < 90)).sum()),
               seconds=round(time.time() - t0, 2))
    return new, rep


def _view_dirs(g):
    d = g.pos - g.cam.pos
    return d / np.maximum(np.linalg.norm(d, axis=-1, keepdims=True), 1e-9)


def check(g, layer, material, new, objects, out_dir):
    """Flat view before / after: does the changed area sit where the layer was painted?"""
    import view
    from scipy.ndimage import distance_transform_edt
    before = view.shade(g, "flat")
    p = os.path.join(out_dir, "_projected_tmp.png"); tex.save(p, new)
    after = view.shade(g, "flat", {material.lower(): p})
    os.remove(p)
    changed = np.abs(after - before).max(-1) > 0.04
    want = (layer[..., 3] > 0.5) & np.isin(g.obj, [scene.object_index(g.sc, o) for o in objects])
    dist_to_want = distance_transform_edt(~want)
    dist_to_changed = distance_transform_edt(~changed)
    cy, cx = np.argwhere(changed).mean(0); wy, wx = np.argwhere(want).mean(0)
    res = dict(changed_px=int(changed.sum()), intended_px=int(want.sum()),
               centre_offset_px=[round(cx - wx, 2), round(cy - wy, 2)],
               changed_outside_intended_mean_px=round(float(dist_to_want[changed].mean()), 2),
               changed_outside_intended_max_px=round(float(dist_to_want[changed].max()), 2),
               intended_not_changed_mean_px=round(float(dist_to_changed[want].mean()), 2))
    tex.save(os.path.join(out_dir, "check_before.png"), before)
    tex.save(os.path.join(out_dir, "check_after.png"), after)
    ov = after.copy(); ov[changed & ~want] = [1, 0, 1]; ov[want & ~changed] = [0, 1, 1]
    tex.save(os.path.join(out_dir, "check_overlay.png"), ov)
    return res


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("material"); ap.add_argument("--png"); ap.add_argument("--doc"); ap.add_argument("--layer")
    ap.add_argument("--object", action="append"); ap.add_argument("--tex"); ap.add_argument("--out", required=True)
    ap.add_argument("--grazing", type=float, default=80.0); ap.add_argument("--ss", type=int, default=2)
    ap.add_argument("--opacity", type=float, default=1.0); ap.add_argument("--check")
    a = ap.parse_args()
    if bool(a.png) == bool(a.doc) or (a.doc and not a.layer):
        raise SystemExit("give either --png layer.png or --doc d.paint.json --layer NAME")
    layer = load_layer(a.png, a.doc, a.layer)
    g = GBuffer(layer.shape[1])
    new, rep = project(layer, a.material, g, a.object, a.tex, a.grazing, a.ss, a.opacity)
    tex.save(a.out, new)
    rep["out"] = os.path.abspath(a.out)
    if a.check:
        os.makedirs(a.check, exist_ok=True)
        rep["check"] = check(g, layer, rep["material"], new, rep["objects"], a.check)
        rep["check"]["images"] = os.path.abspath(a.check)
    print(json.dumps(rep, indent=1))
    if rep["texels_changed"] == 0:
        raise SystemExit("no texel changed: the paint missed every visible part of " + ", ".join(rep["objects"]))


if __name__ == "__main__":
    main()
