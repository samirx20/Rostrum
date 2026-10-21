"""Outline of objects in frame pixels, as polygons for the 2D kit's mask_polygon.

  uv run --with numpy --with pillow --with scipy python -I silhouette.py Jug JugHandle --out silhouette.json

Reads the model's G-buffer (proofs/paint/model) at 1920x1080. Each object becomes one polygon:
the left edge of every row top-down, then the right edge bottom-up (fine for shapes that are one
run per row, like the jug body and its C-shaped handle). Also writes, per object, the row extents
and the 3D normal's x at a few sample points, to place light and shadow shapes by number.
"""
import argparse, json, os, sys
import numpy as np

MODEL = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "model"))
sys.path.insert(0, MODEL)
from gbuffer import GBuffer  # noqa: E402


def outline(mask, step=4):
    rows = [y for y in range(mask.shape[0]) if mask[y].any()]
    left, right = [], []
    for y in rows[::step] + [rows[-1]]:
        xs = np.nonzero(mask[y])[0]
        left.append((int(xs[0]), y)); right.append((int(xs[-1]) + 1, y))
    runs = max(int((np.diff(mask[y].astype(int)) == 1).sum() + mask[y][0]) for y in rows)
    return left + right[::-1], runs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("objects", nargs="+"); ap.add_argument("--out", required=True)
    a = ap.parse_args()
    g = GBuffer()
    names = list(g.sc["objects"])
    out = {}
    for n in a.objects:
        if n not in names:
            raise SystemExit(f"no object {n!r}; objects: {', '.join(names)}")
        m = g.obj == names.index(n)
        poly, runs = outline(m)
        ys, xs = np.nonzero(m)
        out[n] = dict(polygon=poly, bbox=[int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1],
                      max_runs_per_row=runs)
        if runs > 1:
            print(f"warning: {n} has {runs} runs on some row; its polygon fills the gaps between them")
        print(n, out[n]["bbox"], "runs/row", runs)
    with open(a.out, "w") as f:
        json.dump(out, f)
    print("wrote", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
