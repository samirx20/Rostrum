"""`sheet`: contact sheet with time labels."""
import os
import cv2
import numpy as np
from .common import open_video, read_frame, out
from .frames import tile


def run(args):
    cap, fps, n = open_video(args.video)
    step = max(1, int(round(args.every * fps)))
    idx = list(range(int(args.start * fps), min(n, int((args.end or 1e9) * fps) + 1), step))
    tiles = [tile(read_frame(cap, i), f"f{i}  {i / fps:.2f}s", 256) for i in idx]
    h, w = tiles[0].shape[:2]
    cols = args.cols
    while len(tiles) % cols:
        tiles.append(np.zeros((h, w, 3), np.uint8))
    img = np.vstack([np.hstack(tiles[r:r + cols]) for r in range(0, len(tiles), cols)])
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    cv2.imwrite(args.out, img)
    out(dict(cmd="sheet", fps=fps, tiles=len(idx), png=args.out))
