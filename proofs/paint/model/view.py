"""See the textures on the model through the shot camera (quick raster, no Cycles).

  python view.py --out f.png [--mode flat|lit|texel|objects] [--zoom X Y W H] [--size 1920]
                 [--grid N] [--tex Material=path.png ...] [--checker]

  flat     texture colour only (what was painted)
  lit      simple warm sun (make_scene SUN direction) + cool fill, no shadows
  texel    how many texture pixels land on one frame pixel (1 = matched; >1 = detail is lost)
  objects  each object a flat colour, labelled
--zoom is in frame pixels of the 1920x1080 shot; the zoomed view is re-rasterized sharp at
--size px wide. --grid N draws a labelled frame-pixel grid every N frame px.
--tex Jug=my_jug.png shows a texture under work instead of the one in paint/textures.
"""
import argparse, os, sys, time
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene, tex  # noqa: E402
from gbuffer import GBuffer  # noqa: E402

SUN_RGB = np.array([1.0, 0.70, 0.45])     # ~3300 K
FILL_RGB = np.array(scene.S.FILL["color"])
OBJ_RGB = np.array([[.55, .4, .3], [.85, .8, .7], [.3, .5, .8], [.2, .4, .9], [.8, .8, .9], [.3, .3, .3],
                    [.6, .8, .3], [.4, .3, .2], [.8, .7, .3], [.4, .3, .2], [.9, .5, .3], [.4, .3, .2], [.3, .35, .4]])


def to_lin(c): return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def to_srgb(c): c = np.clip(c, 0, 1); return np.where(c <= 0.0031308, c * 12.92, 1.055 * c ** (1 / 2.4) - 0.055)


def albedo(g, overrides=None, checker=False):
    """Per-pixel texture colour (H,W,3 sRGB). Pixels with no texture (Blocker) stay mid grey."""
    overrides = overrides or {}
    out = np.full(g.obj.shape + (3,), 0.5, np.float32)
    uv = g.uv
    for mi, m in enumerate(g.sc["materials"]):
        sel = g.mat == mi
        if not sel.any() or m == "Blocker":
            continue
        path = os.path.join(scene.TEX_DIR, "_checker.png") if checker else overrides.get(m.lower())
        t = tex.material_texture(m, path)
        txy = scene.uv_to_texel(uv[sel], (t.shape[1], t.shape[0]))
        out[sel] = tex.bilinear(t, txy[:, 0], txy[:, 1], wrap=True)
    return out


def shade(g, mode="flat", overrides=None, checker=False):
    if mode == "objects":
        return np.where(g.hit[..., None], OBJ_RGB[np.maximum(g.obj, 0) % len(OBJ_RGB)], 0)
    if mode == "texel":
        sizes = {}
        def size_of(mi):
            m = g.sc["materials"][mi]
            if m == "Blocker":
                return (1, 1)
            if mi not in sizes:
                sizes[mi] = Image.open((overrides or {}).get(m.lower()) or scene.texture_path(m)).size
            return sizes[mi]
        dens = tex.texel_density(g.sc, scene.Camera(), size_of)[np.maximum(g.tri, 0)]
        return np.where(g.hit[..., None], tex.heat(np.log2(np.maximum(dens, 1e-3)), -2, 4), 0)
    a = albedo(g, overrides, checker)
    if mode == "flat":
        return a
    L = np.array(scene.S.SUN["to_sun"])
    n = g.normal
    view = g.pos - g.cam.pos
    n = np.where(((n * view).sum(-1) > 0)[..., None], -n, n)      # light the side we see
    ndl = np.clip(n @ L, 0, 1)[..., None]
    light = SUN_RGB * ndl * 1.1 + FILL_RGB * 0.35 + 0.08
    return np.where(g.hit[..., None], to_srgb(to_lin(a) * light), 0)


def draw_grid(im, cam, step):
    """Labelled frame-pixel grid over a buffer image."""
    d = ImageDraw.Draw(im)
    x0, y0, w, h = cam.crop
    for fx in np.arange(np.ceil(x0 / step) * step, x0 + w, step):
        bx = (fx - x0) * cam.scale
        d.line([(bx, 0), (bx, im.height)], fill=(255, 255, 0), width=1)
        d.text((bx + 3, 3), f"{fx:g}", fill=(255, 255, 0), font_size=14, stroke_width=2, stroke_fill=(0, 0, 0))
    for fy in np.arange(np.ceil(y0 / step) * step, y0 + h, step):
        by = (fy - y0) * cam.scale
        d.line([(0, by), (im.width, by)], fill=(255, 255, 0), width=1)
        d.text((3, by + 3), f"{fy:g}", fill=(255, 255, 0), font_size=14, stroke_width=2, stroke_fill=(0, 0, 0))
    return im


def render(out, mode="flat", zoom=None, size=None, grid=0, overrides=None, checker=False, g=None):
    t = time.time()
    g = g or GBuffer(size or (1600 if zoom else scene.FRAME_W), zoom)
    img = Image.fromarray((np.clip(shade(g, mode, overrides, checker), 0, 1) * 255 + 0.5).astype(np.uint8))
    if grid:
        draw_grid(img, g.cam, grid)
    if mode == "texel":
        tex.legend(img, -2, 4, "texture px per frame px (side)", [(-2, "1/4"), (0, "1"), (2, "4"), (4, "16")])
    if mode == "objects":
        d = ImageDraw.Draw(img)
        for i, n in enumerate(g.sc["objects"]):
            ys, xs = np.nonzero(g.obj == i)
            if len(xs) > 50:
                d.text((xs.mean(), ys.mean()), n, fill=(255, 255, 255), font_size=16, stroke_width=2, stroke_fill=(0, 0, 0))
    img.save(out)
    print(f"{mode} view {g.cam.W}x{g.cam.H} of frame {g.cam.crop} in {time.time() - t:.2f}s -> {os.path.abspath(out)}")
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--mode", default="flat", choices=["flat", "lit", "texel", "objects"])
    ap.add_argument("--zoom", type=float, nargs=4, metavar=("X", "Y", "W", "H"))
    ap.add_argument("--size", type=int)
    ap.add_argument("--grid", type=float, default=0)
    ap.add_argument("--tex", action="append", default=[], metavar="Material=path.png")
    ap.add_argument("--checker", action="store_true")
    a = ap.parse_args()
    ov = {}
    for s in a.tex:
        m, _, p = s.partition("=")
        if not os.path.exists(p):
            raise SystemExit(f"--tex {s}: file not found")
        ov[m.lower()] = p
    render(a.out, a.mode, a.zoom, a.size, a.grid, ov, a.checker)


if __name__ == "__main__":
    main()
