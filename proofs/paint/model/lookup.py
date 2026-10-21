""""Where" both ways between the shot frame and the textures.

  python lookup.py what X Y [--out mark.png]              frame point -> object, material, uv, texel ...
  python lookup.py where MATERIAL TX TY [--object NAME] [--out mark.png]
  python lookup.py where MATERIAL --uv U V [--object NAME] [--out mark.png]

X Y are frame pixels of the 1920x1080 shot (decimals allowed). TX TY are texel column / row
counted from the image's top-left (the texel's centre is used). A texel can show up in several
places (the three pears share material Pear; the table texture repeats): every place is listed,
with visible / hidden and why. --out draws the point(s) on the flat model view.
"""
import argparse, json, os, sys
import numpy as np
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene  # noqa: E402
from gbuffer import GBuffer, perspective  # noqa: E402

GRAZING_DEG = 80.0      # surfaces turned further than this from the camera count as grazing
_sizes = {}


def tex_size(material):
    if material not in _sizes:
        _sizes[material] = Image.open(scene.texture_path(material)).size
    return _sizes[material]


def _facing(n, p, cam):
    to_cam = cam.pos - p
    to_cam = to_cam / np.linalg.norm(to_cam, axis=-1, keepdims=True)
    return np.degrees(np.arccos(np.clip((n * to_cam).sum(-1), -1, 1)))


def screen_to_surface(x, y, g):
    """Frame point -> dict, or SystemExit if it is off the frame or hits nothing textured."""
    if not (0 <= x < scene.FRAME_W and 0 <= y < scene.FRAME_H):
        raise SystemExit(f"({x}, {y}) is off the 1920x1080 frame")
    bx, by = g.cam.frame_to_buf(x, y)
    t = int(g.tri[min(int(by), g.cam.H - 1), min(int(bx), g.cam.W - 1)])
    if t < 0:
        raise SystemExit(f"({x}, {y}) hits no surface")
    sc = g.sc
    fx, fy, zc = g.cam.to_frame(sc["P"][t])
    a, b, c = np.stack([fx, fy], -1)
    area = (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])
    l0 = ((b[0] - x) * (c[1] - y) - (b[1] - y) * (c[0] - x)) / area
    l1 = ((c[0] - x) * (a[1] - y) - (c[1] - y) * (a[0] - x)) / area
    w, _ = perspective(np.array([l0, l1, 1 - l0 - l1]), zc)
    p, uv = w @ sc["P"][t], w @ sc["UV"][t]
    n = w @ sc["N"][t]; n /= np.linalg.norm(n)
    oi = int(sc["tri_obj"][t]); mat = sc["materials"][sc["obj_material"][oi]]
    out = dict(frame=(x, y), object=sc["objects"][oi], material=mat, triangle=t,
               uv=uv.round(5).tolist(), position_cm=p.round(3).tolist(), normal=n.round(4).tolist(),
               distance_cm=round(float(np.linalg.norm(p - g.cam.pos)), 3),
               facing_deg=round(float(_facing(n, p, g.cam)), 1))
    if mat != "Blocker":
        out["texture"] = os.path.basename(scene.texture_path(mat))
        out["texel"] = scene.uv_to_texel(uv, tex_size(mat)).round(2).tolist()
    return out


def uv_to_screen(material, u, v, g, objects=None):
    """UV -> every place on the model with that UV: frame point, object, visible or why hidden."""
    sc = g.sc
    mi = scene.material_index(sc, material)
    obj_ids = [scene.object_index(sc, o) for o in objects] if objects else \
        [i for i, m in enumerate(sc["obj_material"]) if m == mi]
    if objects and any(sc["obj_material"][o] != mi for o in obj_ids):
        raise SystemExit(f"object(s) {objects} do not use material {material}")
    T = np.nonzero(np.isin(sc["tri_obj"], obj_ids))[0]
    UV = sc["UV"][T]
    lo, hi = np.floor(UV.min((0, 1))), np.ceil(UV.max((0, 1)))
    hits = []
    for ku in np.arange(lo[0], hi[0]):                       # repeated textures: every tile
        for kv in np.arange(lo[1], hi[1]):
            q = np.array([u + ku, v + kv])
            a, b, c = UV[:, 0], UV[:, 1], UV[:, 2]
            den = (b[:, 0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (c[:, 0] - a[:, 0])
            ok = np.abs(den) > 1e-14
            den = np.where(ok, den, 1)
            l1 = ((q[0] - a[:, 0]) * (c[:, 1] - a[:, 1]) - (q[1] - a[:, 1]) * (c[:, 0] - a[:, 0])) / den
            l2 = ((b[:, 0] - a[:, 0]) * (q[1] - a[:, 1]) - (b[:, 1] - a[:, 1]) * (q[0] - a[:, 0])) / den
            ins = ok & (l1 >= -1e-9) & (l2 >= -1e-9) & (l1 + l2 <= 1 + 1e-9)
            for i in np.nonzero(ins)[0]:
                hits.append((T[i], np.array([1 - l1[i] - l2[i], l1[i], l2[i]])))
    out, seen = [], set()
    for t, w in hits:
        p = w @ sc["P"][t]
        key = tuple(np.round(p, 3))
        if key in seen:                                        # shared triangle edges
            continue
        seen.add(key)
        n = w @ sc["N"][t]; n /= np.linalg.norm(n)
        x, y, zc = g.cam.to_frame(p)
        oi = int(sc["tri_obj"][t])
        r = dict(object=sc["objects"][oi], frame=[round(float(x), 2), round(float(y), 2)],
                 position_cm=p.round(3).tolist(), facing_deg=round(float(_facing(n, p, g.cam)), 1))
        bx, by = g.cam.frame_to_buf(x, y)
        if not (0 <= bx < g.cam.W and 0 <= by < g.cam.H):
            r["visible"], r["why"] = False, "off frame"
        else:
            j, i = int(by), int(bx)
            front_obj, front_z = int(g.obj[j, i]), float(g.zc[j, i])
            if front_obj == oi and abs(front_z - zc) < 0.01 * zc + 0.05:
                r["visible"] = r["facing_deg"] < 90
                if not r["visible"]:
                    r["why"] = "faces away"
            else:
                r["visible"] = False
                r["why"] = ("on the far side of its own object" if front_obj == oi else
                            "behind " + (sc["objects"][front_obj] if front_obj >= 0 else "nothing?"))
        out.append(r)
    return sorted(out, key=lambda r: (not r["visible"], r["object"]))


def mark(g, points, out):
    import view
    img = view.render(out, "flat", g=g)
    im = Image.open(img); d = ImageDraw.Draw(im)
    for (x, y), vis in points:
        c = (0, 255, 0) if vis else (255, 60, 60)
        d.ellipse([x - 9, y - 9, x + 9, y + 9], outline=c, width=3)
        d.line([(x - 16, y), (x + 16, y)], fill=c); d.line([(x, y - 16), (x, y + 16)], fill=c)
    im.save(out)
    print("marked (green visible, red hidden) ->", os.path.abspath(out))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("what"); w.add_argument("x", type=float); w.add_argument("y", type=float)
    h = sub.add_parser("where"); h.add_argument("material"); h.add_argument("tx", type=float, nargs="?")
    h.add_argument("ty", type=float, nargs="?"); h.add_argument("--uv", type=float, nargs=2)
    h.add_argument("--object", action="append")
    for p in (w, h):
        p.add_argument("--out")
    a = ap.parse_args()
    g = GBuffer()
    if a.cmd == "what":
        r = screen_to_surface(a.x, a.y, g)
        print(json.dumps(r, indent=1))
        if a.out:
            mark(g, [((a.x, a.y), True)], a.out)
        return
    mat = g.sc["materials"][scene.material_index(g.sc, a.material)]
    if a.uv:
        u, v = a.uv
    elif a.tx is not None and a.ty is not None:
        W, H = tex_size(mat)
        if not (0 <= a.tx < W and 0 <= a.ty < H):
            raise SystemExit(f"texel ({a.tx}, {a.ty}) is outside {mat}'s {W}x{H} texture")
        u, v = (a.tx + 0.5) / W, 1 - (a.ty + 0.5) / H
    else:
        raise SystemExit("give TX TY or --uv U V")
    res = uv_to_screen(mat, u, v, g, a.object)
    if not res:
        raise SystemExit(f"uv ({u:.4f}, {v:.4f}) is on no surface of {mat} (outside every UV island)")
    print(json.dumps(dict(material=mat, uv=[round(u, 5), round(v, 5)], places=res), indent=1))
    if a.out:
        mark(g, [(r["frame"], r["visible"]) for r in res], a.out)


if __name__ == "__main__":
    main()
