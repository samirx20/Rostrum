"""UV guides for the painters: for each texture, a transparent PNG (same size as the texture)
with the UV wireframe and labels saying which part of the model lands where.
Use with  paint/look.py guide <texture.png> <guide.png> <out.png>.

  uv run --with pillow python -I guides.py <out_dir>
"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from PIL import Image, ImageDraw
import make_scene as S

SIZES = {"Jug": 2048, "Bowl": 2048, "Pear": 1024, "Cloth": 2048, "Table": 2048}


def profile_marks(profile, v0, v1, names):
    """v of each named profile point (arc length, as lathe() maps it)."""
    import math
    L = [0.0]
    for a, b in zip(profile, profile[1:]):
        L.append(L[-1] + math.dist(a, b))
    return [(v0 + (v1 - v0) * L[i] / L[-1], n) for i, n in names.items()]


MARKS = {
    "Jug": profile_marks(S.JUG, 0.2, 1.0, {0: "bottom centre", 1: "base edge", 4: "belly (widest)",
                                            7: "neck", 9: "lip (top rim)", 13: "inside", 18: "inside floor"})
           + [(0.09, "HANDLE strip (u along handle top->bottom, v around)")],
    "Bowl": profile_marks(S.BOWL, 0.0, 1.0, {1: "foot", 5: "outside wall", 7: "rim",
                                              10: "inside wall", 12: "inside floor centre"}),
    "Pear": profile_marks(S.PEAR, 0.0, 0.9, {0: "bottom", 3: "widest", 6: "neck", 9: "top"})
            + [(0.96, "STEM strip")],
}
U_MARKS = {"Jug": {0.5: "front (camera)", 0.25: "handle side", 0.0: "back seam", 0.75: "far side"},
           "Bowl": {0.5: "front", 0.0: "back seam"}, "Pear": {0.5: "front*", 0.0: "seam"}}


def draw(name, mesh_list, out_dir):
    n = SIZES[name]
    im = Image.new("RGBA", (n, n), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    for m in mesh_list:
        k = 0
        for c in m.counts:
            f = m.idx[k:k + c]; k += c
            pts = [(m.UV[i][0] * n, (1 - m.UV[i][1]) * n) for i in f]
            d.polygon(pts, outline=(255, 255, 255, 70))
    for v, label in MARKS.get(name, []):
        y = (1 - v) * n
        d.line([(0, y), (n, y)], fill=(255, 220, 0, 230), width=3)
        d.text((10, y - 26), f"{label}  v={v:.2f}", fill=(255, 255, 0, 255), font_size=max(16, n // 64))
    for u, label in U_MARKS.get(name, {}).items():
        x = u * n
        d.line([(x, 0), (x, n)], fill=(0, 230, 255, 230), width=3)
        d.text((x + 8, 8), f"{label} u={u:.2f}", fill=(0, 255, 255, 255), font_size=max(16, n // 64))
    if name == "Table":
        d.text((20, 20), "Table top: whole image = 75 x 75 cm of plank surface, repeats.\n"
                         "Image x = table left->right, image y = far->near. Sides reuse it.",
               fill=(255, 255, 0, 255), font_size=36)
    if name == "Cloth":
        d.text((20, 20), "Cloth 38 x 30 cm: image x = cloth length, image y = width.",
               fill=(255, 255, 0, 255), font_size=36)
    path = os.path.join(out_dir, f"{name.lower()}_guide.png")
    im.save(path)
    print("wrote", path)


def main():
    out_dir = sys.argv[1]
    os.makedirs(out_dir, exist_ok=True)
    groups = {}
    for _, (mesh, mat, *_rest) in S.parts().items():
        if mesh not in groups.setdefault(mat, []):
            groups[mat].append(mesh)
    for name, meshes in groups.items():
        draw(name, meshes, out_dir)


if __name__ == "__main__":
    main()
