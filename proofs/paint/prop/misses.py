"""Stroke by stroke: where did each stroke land on the model, compared with where it was painted?

  uv run --with numpy --with pillow --with scipy python -I misses.py jug.paint.json 120 121 130 ... [--out misses.json]

Every named stroke's coverage (> 0.5) is painted in its own code colour onto a flat grey copy of the jug
texture in ONE projection (Jug + JugHandle), the flat model view is rendered, and each code colour is
found again in the frame. Per stroke: painted px, landed px, centre offset (landed - painted, frame
px), share of the painted area that shows the stroke, and the farthest landed pixel from the painted
area. A clean landing has offset ~0 and reach ~100 %; grazing edges and silhouettes lower the reach.
"""
import argparse, itertools, json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL = os.path.normpath(os.path.join(HERE, "..", "model")); KIT = os.path.normpath(os.path.join(HERE, "..", "kit"))
sys.path[:0] = [MODEL, KIT]
import scene, tex, view  # noqa: E402
from gbuffer import GBuffer  # noqa: E402
from project import project  # noqa: E402
from doc import Doc  # noqa: E402
from scipy.ndimage import distance_transform_edt  # noqa: E402

OBJECTS = ["Jug", "JugHandle"]
CODES = [c for c in itertools.product((0.0, 0.33, 0.67, 1.0), repeat=3) if np.ptp(c) > 0.3]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("doc"); ap.add_argument("ids", nargs="+", type=int); ap.add_argument("--out")
    a = ap.parse_args()
    if len(a.ids) > len(CODES):
        raise SystemExit(f"at most {len(CODES)} strokes per run; strokes that overlap each other should go in separate runs")
    d = Doc.open(a.doc)
    g = GBuffer()
    on = np.isin(g.obj, [scene.object_index(g.sc, o) for o in OBJECTS])
    layer = np.zeros((g.cam.H, g.cam.W, 4), np.float32)
    covs = {}
    for sid, c in zip(a.ids, CODES):
        cov = d.stroke_coverage(sid) > 0.5
        covs[sid] = (cov, np.array(c))
        layer[cov] = [*c, 1.0]
    grey = os.path.join(HERE, "_misses_grey.png")
    t = tex.load(os.path.join(scene.TEX_DIR, "jug.png"))
    tex.save(grey, np.full_like(t, 0.5))
    try:
        new, _ = project(layer, "Jug", g, OBJECTS, grey)
        coded = tex.save(os.path.join(HERE, "_misses_coded.png"), new)
        after = view.shade(g, "flat", {"jug": coded})
        os.remove(coded)
    finally:
        os.remove(grey)
    # each frame pixel goes to the nearest code colour or the grey ground (a small mark's edge is
    # blended with the grey by texture filtering; an exact colour match would miss it)
    palette = np.array([[0.5, 0.5, 0.5]] + [c for _, c in covs.values()])
    best = np.full(after.shape[:2], np.inf, np.float32); label = np.zeros(after.shape[:2], np.int32)
    for i, p in enumerate(palette):
        dist = ((after - p) ** 2).sum(-1)
        label[dist < best] = i; best = np.minimum(best, dist)
    rows = []
    for idx, (sid, (cov, c)) in enumerate(covs.items(), 1):
        want = cov & on
        got = (label == idx) & on
        r = dict(stroke=sid, painted_px=int(cov.sum()), on_object_px=int(want.sum()), landed_px=int(got.sum()))
        if got.any() and want.any():
            gy, gx = np.argwhere(got).mean(0); wy, wx = np.argwhere(want).mean(0)
            r.update(centre_painted=[round(wx, 1), round(wy, 1)], centre_offset_px=[round(gx - wx, 1), round(gy - wy, 1)],
                     reach_pct=round(100 * (got & want).sum() / want.sum(), 1),
                     farthest_stray_px=round(float(distance_transform_edt(~want)[got].max()), 1))
        rows.append(r)
        print(json.dumps(r))
    if a.out:
        json.dump(rows, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
