"""Eyes on the picture: frame strips around a time, and a contact sheet."""
import os

import numpy as np

from .video import open_video, read_frame, tile, write_png

STRIP_TILE_W = 320
SHEET_TILE_W = 256


def frames(video, at, span=2, out_dir=".", step=1):
    """Strip of frames around time `at` (s): `span` frames each side, `step` frames apart, each
    labelled with its frame number and time (centre marked <<). Returns facts + the strip PNG path."""
    cap, fps, n = open_video(video)
    try:
        c = int(round(at * fps))
        if not 0 <= c < n:
            raise ValueError(f"{video}: time {at}s is outside the video (0 to {n / fps:.2f}s)")
        tiles = []
        for j in range(c - span * step, c + span * step + 1, step):
            j = min(max(j, 0), n - 1)
            tiles.append(tile(read_frame(cap, j, video), f"f{j}  {j / fps:.2f}s" + ("  <<" if j == c else ""),
                              STRIP_TILE_W))
        png = write_png(os.path.join(out_dir, f"strip_{c:05d}.png"), np.hstack(tiles))
    finally:
        cap.release()
    return {"fps": round(fps, 3), "frame_count": n, "at_s": at, "frame": c, "png": png}


def sheet(video, out_png, every=0.5, start=0.0, end=None, cols=6):
    """Contact sheet: one labelled tile every `every` seconds in [start, end]."""
    cap, fps, n = open_video(video)
    try:
        step = max(1, int(round(every * fps)))
        idx = list(range(int(start * fps), min(n, int((end if end is not None else 1e9) * fps) + 1), step))
        if not idx:
            raise ValueError(f"{video}: no frames between {start}s and {end}s")
        tiles = [tile(read_frame(cap, i, video), f"f{i}  {i / fps:.2f}s", SHEET_TILE_W) for i in idx]
    finally:
        cap.release()
    h, w = tiles[0].shape[:2]
    while len(tiles) % cols:
        tiles.append(np.zeros((h, w, 3), np.uint8))
    img = np.vstack([np.hstack(tiles[r:r + cols]) for r in range(0, len(tiles), cols)])
    return {"fps": round(fps, 3), "frame_count": n, "tiles": len(idx), "every_s": every,
            "png": write_png(out_png, img)}
