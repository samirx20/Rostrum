"""`motion`: dense optical flow per frame, moving-region box, contact candidates."""
import json
import os
import cv2
import numpy as np
from scipy.signal import find_peaks
from .common import open_video, out, fail

SCALE_W = 320       # flow is computed at this width
THRESH = 0.35       # px/frame at flow scale: below = still
GRID = (4, 8)       # rows, cols for the coarse energy grid


def flow_series(path):
    cap, fps, n = open_video(path)
    k = None
    prev = prev_h = None
    rows = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        if k is None:
            k = fr.shape[1] / SCALE_W
        g = cv2.cvtColor(cv2.resize(fr, (SCALE_W, int(fr.shape[0] / k)), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY)
        g = cv2.GaussianBlur(g, (3, 3), 0)
        i = len(rows)
        h32 = cv2.calcHist([g], [0], None, [32], [0, 256]).ravel(); h32 /= h32.sum()
        r = dict(frame=i, cut=0.0, energy=0.0, speed=0.0, peak=0.0, area=0.0, centroid=None, bbox=None, grid=None)
        if prev is not None:
            r["cut"] = float(np.abs(h32 - prev_h).sum() / 2 + np.abs(g.astype(np.int16) - prev).mean() / 255)
            f = cv2.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0)
            mag = np.linalg.norm(f, axis=2)
            m = mag > THRESH
            h, w = mag.shape
            r.update(energy=float(mag.sum() * k / (h * w)), area=float(m.mean()))
            if m.sum() > 20:
                ys, xs = np.nonzero(m)
                wts = mag[m]
                r["speed"] = float(wts.mean() * k)
                r["peak"] = float(np.percentile(wts, 95) * k)
                r["centroid"] = [float(np.average(xs, weights=wts) * k), float(np.average(ys, weights=wts) * k)]
                r["bbox"] = [int(np.percentile(xs, 2) * k), int(np.percentile(ys, 2) * k),
                             int(np.percentile(xs, 98) * k), int(np.percentile(ys, 98) * k)]
            gr = np.array([[mag[a * h // GRID[0]:(a + 1) * h // GRID[0], b * w // GRID[1]:(b + 1) * w // GRID[1]].mean()
                            for b in range(GRID[1])] for a in range(GRID[0])]) * k
            r["grid"] = np.round(gr, 2).tolist()
        rows.append(r)
        prev, prev_h = g, h32
    cap.release()
    return rows, fps


def candidates(rows, fps, min_prev=3.0, min_drop=3.0, rel=0.3):
    """Contact = a sharp fall in speed (stop) or sharp rise (start), 1 frame precise."""
    sp = np.array([r["peak"] for r in rows])
    d = np.diff(sp, prepend=sp[0])
    stops, _ = find_peaks(-d, height=min_drop, distance=3)
    starts, _ = find_peaks(d, height=min_drop, distance=3)
    res = []
    for kind, idxs in (("stop", stops), ("start", starts)):
        for i in idxs:
            ref = sp[max(0, i - 3):i].max() if kind == "stop" else sp[i:i + 3].max()
            if ref < min_prev or abs(d[i]) < rel * max(sp[i - 1], sp[i]):
                continue
            res.append(dict(kind=kind, frame=int(i), time_s=round(i / fps, 3), delta=round(float(d[i]), 2),
                            speed_before=round(float(sp[i - 1]), 2), speed_after=round(float(sp[i]), 2),
                            at=[round(v) for v in rows[i]["centroid"]] if rows[i]["centroid"] else None))
    return sorted(res, key=lambda c: c["frame"])


def cuts(rows, fps, thr=0.12):
    """Frames where the picture jumps (edit cut or a hand/sleeve covering the lens). No contact sound is valid across one."""
    c = np.array([r["cut"] for r in rows])
    idx, _ = find_peaks(c, height=thr, distance=4)
    return [dict(frame=int(i), time_s=round(i / fps, 3), jump=round(float(c[i]), 2)) for i in idx]


def plot(rows, cands, fps, png, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    t = np.arange(len(rows)) / fps
    sp = np.array([r["peak"] for r in rows])
    en = np.array([r["energy"] for r in rows])
    d = np.diff(sp, prepend=sp[0])
    fig, ax = plt.subplots(3, 1, figsize=(18, 8), sharex=True)
    ax[0].plot(t, en, c="#1b6ca8"); ax[0].set_ylabel("motion energy")
    ax[1].plot(t, sp, c="#c0392b"); ax[1].set_ylabel("fast-part speed px/frame")
    ax[2].plot(t, d, c="#555"); ax[2].set_ylabel("speed change")
    for c in cands:
        col = "#e67e22" if c["kind"] == "stop" else "#27ae60"
        for a in ax:
            a.axvline(c["time_s"], c=col, lw=.7, alpha=.7)
        ax[1].text(c["time_s"], sp.max() * (0.95 if c["kind"] == "stop" else 0.8), f'{c["frame"]}',
                   rotation=90, fontsize=7, color=col, va="top", ha="right")
    ax[2].set_xlabel("seconds (orange = stop/contact, green = start; labels = frame number)")
    fig.suptitle(title); fig.tight_layout(); fig.savefig(png, dpi=90); plt.close(fig)


def run(args):
    rows, fps = flow_series(args.video)
    if not rows:
        fail("no frames")
    cands = candidates(rows, fps)
    cut_list = cuts(rows, fps)
    os.makedirs(args.outdir, exist_ok=True)
    png = os.path.join(args.outdir, "motion.png")
    plot(rows, cands, fps, png, os.path.basename(args.video))
    jp = os.path.join(args.outdir, "motion.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(dict(fps=fps, frames=rows, candidates=cands, cuts=cut_list), f)
    out(dict(cmd="motion", fps=fps, n_frames=len(rows), json=jp, plot=png, cuts=cut_list, candidates=cands))
