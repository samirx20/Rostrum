"""`frames`: strips of frames around given times, plus a zoom on the moving region."""
import json
import os
import cv2
import numpy as np
from .common import open_video, read_frame, out, fail

TILE_W = 400


def label(img, text):
    cv2.rectangle(img, (0, 0), (img.shape[1], 18), (0, 0, 0), -1)
    cv2.putText(img, text, (4, 13), cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1, cv2.LINE_AA)
    return img


def tile(fr, text, w=TILE_W):
    h = int(fr.shape[0] * w / fr.shape[1])
    return label(cv2.resize(fr, (w, h), interpolation=cv2.INTER_AREA), text)


def region_for(motion_json, i):
    """Union of moving-region boxes over frames i-2..i+1 (source px)."""
    if not motion_json or not os.path.exists(motion_json):
        return None
    rows = json.load(open(motion_json, encoding="utf-8"))["frames"]
    bs = [r["bbox"] for r in rows[max(0, i - 2):i + 2] if r["bbox"]]
    if not bs:
        return None
    b = np.array(bs)
    return [int(b[:, 0].min()), int(b[:, 1].min()), int(b[:, 2].max()), int(b[:, 3].max())]


def strip(cap, fps, n, center, window, crop=None, step=1):
    tiles = []
    for j in range(center - window * step, center + window * step + 1, step):
        j = min(max(j, 0), n - 1)
        fr = read_frame(cap, j)
        if crop:
            x0, y0, x1, y1 = crop
            fr = fr[y0:y1, x0:x1]
        tiles.append(tile(fr, f"f{j}  {j / fps:.2f}s" + ("  <<" if j == center else ""), 240 if crop else TILE_W))
    return np.hstack(tiles)


def run(args):
    cap, fps, n = open_video(args.video)
    os.makedirs(args.outdir, exist_ok=True)
    res = []
    for t in [float(x) for x in args.at.split(",")]:
        c = int(round(t * fps))
        if not 0 <= c < n:
            fail(f"time {t}s outside the video")
        p = os.path.join(args.outdir, f"strip_{c:04d}.png")
        cv2.imwrite(p, strip(cap, fps, n, c, args.window, step=args.step))
        e = dict(time_s=t, frame=c, strip=p)
        reg = region_for(args.motion, c)
        if reg:
            pad = 60
            H, W = int(cap.get(4)), int(cap.get(3))
            reg = [max(0, reg[0] - pad), max(0, reg[1] - pad), min(W, reg[2] + pad), min(H, reg[3] + pad)]
            if reg[2] - reg[0] > 40 and reg[3] - reg[1] > 40:
                zp = os.path.join(args.outdir, f"zoom_{c:04d}.png")
                cv2.imwrite(zp, strip(cap, fps, n, c, args.window, crop=reg, step=args.step))
                e.update(zoom=zp, region=reg)
        res.append(e)
    out(dict(cmd="frames", fps=fps, items=res))
