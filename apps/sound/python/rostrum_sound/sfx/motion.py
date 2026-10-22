"""motion: how much moves per frame, and the frames where a moving thing stops or starts (contact)."""
import os

import numpy as np

from ..listen.dsp_events import find_peaks
from ..listen.plot import pyplot
from .video import cv2, open_video

FLOW_W = 320        # optical flow is computed at this width
MOVING_PX = 0.35    # px/frame (at flow scale) under which a pixel counts as still
CUT_JUMP = 0.12     # picture change over this = an edit cut or something covering the lens


def flow_series(video):
    """Per frame: motion energy, speed of the fast part (px/frame, source scale), picture jump,
    centroid of what moves -> (rows, fps)."""
    cap, fps, _ = open_video(video)
    cv = cv2()
    rows, prev, prev_h, k = [], None, None, None
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        k = k or fr.shape[1] / FLOW_W
        g = cv.GaussianBlur(cv.cvtColor(cv.resize(fr, (FLOW_W, int(fr.shape[0] / k)),
                            interpolation=cv.INTER_AREA), cv.COLOR_BGR2GRAY), (3, 3), 0)
        hist = cv.calcHist([g], [0], None, [32], [0, 256]).ravel()
        hist /= hist.sum()
        r = {"frame": len(rows), "energy": 0.0, "speed": 0.0, "jump": 0.0, "at": None}
        if prev is not None:
            r["jump"] = float(np.abs(hist - prev_h).sum() / 2 + np.abs(g.astype(np.int16) - prev).mean() / 255)
            mag = np.linalg.norm(cv.calcOpticalFlowFarneback(prev, g, None, 0.5, 3, 15, 3, 5, 1.2, 0), axis=2)
            r["energy"] = float(mag.sum() * k / mag.size)
            moving = mag > MOVING_PX
            if moving.sum() > 20:
                ys, xs = np.nonzero(moving)
                w = mag[moving]
                r["speed"] = float(np.percentile(w, 95) * k)
                r["at"] = [round(float(np.average(xs, weights=w) * k)), round(float(np.average(ys, weights=w) * k))]
        rows.append(r)
        prev, prev_h = g, hist
    cap.release()
    return rows, fps


def candidates(rows, fps, min_speed=3.0, min_drop=3.0, rel=0.3, min_confidence=0.0):
    """Contact = a sharp fall in speed ("stop", an impact) or rise ("start"), one frame precise.
    confidence 0-1: how big the change is against the speed around it."""
    sp = np.array([r["speed"] for r in rows])
    d = np.diff(sp, prepend=sp[0])
    out = []
    for kind, sign in (("stop", -1), ("start", 1)):
        idx = find_peaks(sign * d, height=min_drop, distance=3)
        for i in idx:
            ref = sp[max(0, i - 3):i].max() if kind == "stop" else sp[i:i + 3].max()
            big = max(sp[i - 1], sp[i])
            if ref < min_speed or abs(d[i]) < rel * big:
                continue
            conf = round(float(min(1.0, abs(d[i]) / max(big, 1e-6))), 2)
            if conf < min_confidence:
                continue
            out.append({"kind": kind, "frame": int(i), "time_s": round(i / fps, 3),
                        "speed_before": round(float(sp[i - 1]), 2), "speed_after": round(float(sp[i]), 2),
                        "at": rows[i]["at"], "confidence": conf})
    return sorted(out, key=lambda c: c["frame"])


def _plot(rows, cands, fps, png, title):
    t = np.arange(len(rows)) / fps
    en, sp = np.array([r["energy"] for r in rows]), np.array([r["speed"] for r in rows])
    plt = pyplot()
    fig, ax = plt.subplots(3, 1, figsize=(16, 8), sharex=True)
    ax[0].plot(t, en, c="#1b6ca8"); ax[0].set_ylabel("motion energy")
    ax[1].plot(t, sp, c="#c0392b"); ax[1].set_ylabel("fast-part speed (px/frame)")
    ax[2].plot(t, np.diff(sp, prepend=sp[0]), c="#555"); ax[2].set_ylabel("speed change")
    for c in cands:
        col = "#e67e22" if c["kind"] == "stop" else "#27ae60"
        for a in ax:
            a.axvline(c["time_s"], c=col, lw=0.8, alpha=0.7)
        ax[1].text(c["time_s"], sp.max() * (0.95 if c["kind"] == "stop" else 0.8), str(c["frame"]),
                   rotation=90, fontsize=8, color=col, va="top", ha="right")
    ax[2].set_xlabel("seconds  (orange = stop / contact, green = start, numbers = frame)")
    fig.suptitle(title)
    fig.tight_layout()
    fig.savefig(png, dpi=90)
    plt.close(fig)


def motion(video, out_dir, **options):
    """Motion curve picture + contact candidates for a video. options: min_speed, min_drop, rel,
    min_confidence (see `candidates`; raise min_confidence on a busy shot). Returns fps, frame count, `candidates` (stop/start with time, frame,
    confidence), `cuts` (picture jumps: no contact sound is valid across one) and the PNG path."""
    rows, fps = flow_series(video)
    if not rows:
        raise ValueError(f"{video}: no frames could be read")
    cands = candidates(rows, fps, **options)
    jump = np.array([r["jump"] for r in rows])
    cuts = [{"frame": int(i), "time_s": round(i / fps, 3), "jump": round(float(jump[i]), 2)}
            for i in find_peaks(jump, height=CUT_JUMP, distance=4)]
    os.makedirs(out_dir, exist_ok=True)
    png = os.path.join(out_dir, "motion.png")
    _plot(rows, cands, fps, png, os.path.basename(os.fspath(video)))
    return {"fps": round(fps, 3), "frame_count": len(rows), "candidates": cands, "cuts": cuts, "png": png}
