"""Coverage map of one material's texture: which texels the camera sees and how big each one
appears, which texels were painted, and where the UV islands' edges (seams) run.

  python coverage.py MATERIAL --out cover.png [--object NAME ...] [--tex current.png]
                     [--before old.png --after new.png] [--grazing 80]

Picture: the texture in grey; texels the camera sees are tinted by screen size (blue = many
texels share one frame pixel, detail is lost; red = one texel covers several frame pixels, paint
there must be smooth); black = never seen; magenta = painted (before vs after); white lines = UV
island edges (paint stops there; the next island may be far away in the image).
"""
import argparse, json, os, sys, time
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene, tex  # noqa: E402
from gbuffer import GBuffer  # noqa: E402
from project import uv_samples, visible  # noqa: E402


def island_edges(sc, tris):
    """UV edges used by exactly one triangle (island borders), as (n,2,2) uv segments."""
    uv = np.round(sc["UV"][tris], 6)
    e = np.concatenate([uv[:, [0, 1]], uv[:, [1, 2]], uv[:, [2, 0]]])          # (n, 2 ends, uv)
    swap = (e[:, 0, 0] > e[:, 1, 0]) | ((e[:, 0, 0] == e[:, 1, 0]) & (e[:, 0, 1] > e[:, 1, 1]))
    e[swap] = e[swap][:, ::-1]
    _, inv, cnt = np.unique(e.reshape(len(e), 4), axis=0, return_inverse=True, return_counts=True)
    return e[cnt[inv.ravel()] == 1]


def coverage(material, g, objects=None, texture=None, before=None, after=None, grazing=80.0):
    sc = g.sc
    mi = scene.material_index(sc, material)
    material = sc["materials"][mi]
    obj_ids = [scene.object_index(sc, o) for o in objects] if objects else \
        [i for i, m in enumerate(sc["obj_material"]) if m == mi]
    T = tex.load(texture or scene.texture_path(material))[..., :3]
    H, W = T.shape[:2]
    tris = np.nonzero(np.isin(sc["tri_obj"], obj_ids))[0]
    tix, tri, l = uv_samples(sc, tris, (W, H), 1)
    p = np.einsum("nk,nkc->nc", l, sc["P"][tri])
    n = np.einsum("nk,nkc->nc", l, sc["N"][tri]); n /= np.linalg.norm(n, axis=1, keepdims=True)
    _, _, seen, ang = visible(g, tri, p, n)
    ok = seen & (ang < grazing)
    dens = tex.texel_density(sc, scene.Camera(), lambda m: (W, H) if m == mi else (1, 1))[tri]
    N = W * H
    used = np.zeros(N, bool); used[tix] = True
    vis = np.zeros(N, bool); vis[tix[ok]] = True
    size = np.zeros(N); size[tix[ok]] = -np.log2(np.maximum(dens[ok], 1e-6))   # log2 frame px per texel side
    grey = T.mean(-1, keepdims=True) * 0.6 + 0.2
    img = np.where(used.reshape(H, W, 1), grey * 0.55, 0.08 + 0 * grey)
    heat = tex.heat(size.reshape(H, W), -4, 2)
    img = np.where(vis.reshape(H, W, 1), grey * 0.45 + heat * 0.55, img)
    rep = dict(material=material, objects=[sc["objects"][o] for o in obj_ids], texture=f"{W}x{H}",
               texels_on_model=int(used.sum()), texels_seen=int(vis.sum()),
               seen_pct_of_model=round(100 * vis.sum() / max(used.sum(), 1), 1),
               median_texels_per_frame_px_side=round(float(np.median(dens[ok])) if ok.any() else 0, 2))
    if before is not None:
        b, a = tex.load(before)[..., :3], tex.load(after)[..., :3]
        if b.shape != a.shape or b.shape[:2] != (H, W):
            raise SystemExit(f"--before / --after must both be {W}x{H}")
        painted = np.abs(a - b).max(-1) > 1.5 / 255
        img[painted] = img[painted] * 0.3 + np.array([1.0, 0.0, 1.0]) * 0.7
        rep.update(texels_painted=int(painted.sum()),
                   painted_but_unseen=int((painted.ravel() & ~vis).sum()))
    im = Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8))
    d = ImageDraw.Draw(im)
    for (u0, v0), (u1, v1) in island_edges(sc, tris):
        d.line([(u0 * W, (1 - v0) * H), (u1 * W, (1 - v1) * H)], fill=(255, 255, 255), width=2)
    tex.legend(im, -4, 2, "frame px per texel (side)", [(-4, "1/16"), (-2, "1/4"), (0, "1"), (2, "4")])
    return im, rep


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("material"); ap.add_argument("--out", required=True); ap.add_argument("--object", action="append")
    ap.add_argument("--tex"); ap.add_argument("--before"); ap.add_argument("--after")
    ap.add_argument("--grazing", type=float, default=80.0)
    a = ap.parse_args()
    if bool(a.before) != bool(a.after):
        raise SystemExit("give both --before and --after")
    t = time.time()
    im, rep = coverage(a.material, GBuffer(), a.object, a.tex, a.before, a.after, a.grazing)
    im.save(a.out)
    rep.update(seconds=round(time.time() - t, 2), out=os.path.abspath(a.out))
    print(json.dumps(rep, indent=1))


if __name__ == "__main__":
    main()
