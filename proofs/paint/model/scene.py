"""The still life (proofs/3d-painterly/scene) as numpy triangles, plus the shot camera.

One source of truth for: which objects exist, their material, world-space triangles (points,
normals, UVs), the camera projection, and texture file paths. Read-only use of make_scene.py.

Screen coordinates everywhere in model/ are FRAME PIXELS of the 1920x1080 shot (x right,
y down, pixel (i, j) has its centre at (i + 0.5, j + 0.5)), whatever resolution a buffer has.
Texture coordinates: u right, v up; texel x = u * W, texel y = (1 - v) * H (v = 0 is the image
bottom row, as Cycles reads `st`). UVs outside 0..1 (the table) repeat.
"""
import math, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SCENE_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "3d-painterly", "scene"))
TEX_DIR = os.path.normpath(os.path.join(HERE, "..", "..", "3d-painterly", "paint", "textures"))
sys.path.insert(0, SCENE_DIR)
import make_scene as S  # noqa: E402

FRAME_W, FRAME_H = 1920, 1080          # the Cycles frame; all screen coordinates use it


def _rot(deg, axis):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    if axis == "y":
        return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def _triangles(m):
    """Fan-triangulate a geo.Mesh -> vertex index triples."""
    tris, k = [], 0
    for c in m.counts:
        f = m.idx[k:k + c]; k += c
        tris += [(f[0], f[i], f[i + 1]) for i in range(1, c - 1)]
    return np.array(tris, dtype=np.int64)


def _background_mesh():
    """BackgroundCard exactly as make_scene.background_card() writes it."""
    from geo import Mesh
    c = S.CAMERA
    fwd, right, up = S.frame(c["pos"], c["target"])
    hw = S.BG_DISTANCE * c["h_aperture"] / (2 * c["focal"]) * 1.06
    hh = S.BG_DISTANCE * c["v_aperture"] / (2 * c["focal"]) * 1.06
    ctr = [c["pos"][k] + fwd[k] * S.BG_DISTANCE for k in range(3)]
    m = Mesh()
    m.P = [tuple(ctr[k] + sx * hw * right[k] + sy * hh * up[k] for k in range(3))
           for sx, sy in [(-1, -1), (1, -1), (1, 1), (-1, 1)]]
    m.N = [tuple(-x for x in fwd)] * 4
    m.UV = [(0, 0), (1, 0), (1, 1), (0, 1)]
    m.counts, m.idx = [4], [0, 1, 2, 3]
    return m


def load():
    """All triangles of the scene. Returns dict:
    objects [names], materials [names], obj_material (O,), tri_obj (T,), P/N (T,3,3) world, UV (T,3,2)."""
    parts = dict(S.parts())
    parts["BackgroundCard"] = (_background_mesh(), "Background", (0, 0, 0), 0, 0, 1)
    objects, mats, obj_mat, Ps, Ns, UVs, tobj = [], [], [], [], [], [], []
    for oi, (name, (m, mat, t, ry, rz, s)) in enumerate(parts.items()):
        R = _rot(ry, "y") @ _rot(rz, "z")      # xformOpOrder translate, rotY, rotZ, scale
        P = np.asarray(m.P, float) * s @ R.T + np.asarray(t, float)
        N = np.asarray(m.N, float) @ R.T
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
        tri = _triangles(m)
        objects.append(name)
        if mat not in mats:
            mats.append(mat)
        obj_mat.append(mats.index(mat))
        Ps.append(P[tri]); Ns.append(N[tri]); UVs.append(np.asarray(m.UV, float)[tri])
        tobj.append(np.full(len(tri), oi, np.int32))
    return dict(objects=objects, materials=mats, obj_material=np.array(obj_mat, np.int32),
                tri_obj=np.concatenate(tobj), P=np.concatenate(Ps), N=np.concatenate(Ns),
                UV=np.concatenate(UVs))


def object_index(sc, name):
    if name not in sc["objects"]:
        raise SystemExit(f"unknown object {name!r}; objects: {', '.join(sc['objects'])}")
    return sc["objects"].index(name)


def material_index(sc, name):
    low = [m.lower() for m in sc["materials"]]
    if name.lower() not in low:
        raise SystemExit(f"unknown material {name!r}; materials: {', '.join(sc['materials'])}")
    return low.index(name.lower())


def texture_path(material):
    p = os.path.join(TEX_DIR, material.lower() + ".png")
    if not os.path.exists(p):
        raise SystemExit(f"no texture for material {material!r} (looked for {p})")
    return p


class Camera:
    """The USD shot camera (look-at, world up +Y). An output buffer of W x H pixels shows the frame
    rectangle `crop` = (x0, y0, w, h) in frame pixels (default the whole 1920x1080 frame)."""

    def __init__(self, W=FRAME_W, H=None, crop=None):
        c = S.CAMERA
        self.pos = np.array(c["pos"], float)
        fwd, right, up = S.frame(c["pos"], c["target"])
        self.fwd, self.right, self.up = (np.array(v, float) for v in (fwd, right, up))
        self.fx = c["focal"] / (c["h_aperture"] / 2) * FRAME_W / 2   # frame px per unit tan
        self.fy = c["focal"] / (c["v_aperture"] / 2) * FRAME_H / 2
        self.crop = tuple(float(v) for v in (crop or (0, 0, FRAME_W, FRAME_H)))
        self.W = int(W)
        self.H = int(H) if H else int(round(self.W * self.crop[3] / self.crop[2]))
        self.scale = self.W / self.crop[2]                             # buffer px per frame px

    def to_frame(self, P):
        """World points (...,3) -> frame px x, y and camera depth z (along the view axis)."""
        d = np.asarray(P, float) - self.pos
        xc, yc, zc = d @ self.right, d @ self.up, d @ self.fwd
        zs = np.where(np.abs(zc) < 1e-9, 1e-9, zc)
        return FRAME_W / 2 + self.fx * xc / zs, FRAME_H / 2 - self.fy * yc / zs, zc

    def frame_to_buf(self, x, y):
        return (np.asarray(x) - self.crop[0]) * self.scale, (np.asarray(y) - self.crop[1]) * self.scale

    def buf_to_frame(self, bx, by):
        return np.asarray(bx) / self.scale + self.crop[0], np.asarray(by) / self.scale + self.crop[1]

    def ray(self, x, y):
        """Unit view direction through frame point (x, y)."""
        d = (self.fwd + self.right * (x - FRAME_W / 2) / self.fx - self.up * (y - FRAME_H / 2) / self.fy)
        return d / np.linalg.norm(d)


def uv_to_texel(uv, size):
    """uv (...,2) -> texel coordinates (continuous, wrapped into the image) for size (W, H)."""
    W, H = size
    w = np.where((uv >= 0) & (uv <= 1), uv, np.mod(uv, 1.0))   # keep 1.0 = top row, repeat outside
    return np.stack([w[..., 0] * W, (1.0 - w[..., 1]) * H], -1)
