"""The GIF encoder: a program the engine pipes its RGBA8 frames into (formats.gif_encode builds the command), run as
`python -I gif_encode.py <out> <w> <h> <fps> <out_w> <out_h> <out_fps>`. Standalone (Pillow and numpy only).

What makes a GIF small at the same look (measured on the sample: the old one-palette-per-frame encoder made 17.7 MB):
- the size and the frame rate are chosen first (the picture is scaled with a box filter; frames are dropped evenly, each
  kept frame lasts until the next kept one starts, so the GIF's length is the scene's);
- ONE palette for the whole GIF, made from frames spread over its length, so a still part costs nothing between frames
  (Pillow then writes only the changed rectangle of each frame, and merges identical frames);
- an ORDERED dither (a fixed 8×8 pattern, the same on every frame): gradients stay smooth, and a pattern that does not
  move does not change between frames, where an error-spreading dither shimmers and fills every frame with new noise;
- transparency is one palette slot (alpha < 128): the palette gets 255 colours then.
Frames wait in a temporary file at the output size (a full-HD GIF never holds its frames in memory).
- the work on a frame (scaling, then colour matching) runs on a few threads at once, a few frames ahead and always written
  in order: Pillow and numpy let go of the interpreter lock for it. One thread did a full-HD GIF at about 14 pictures a second.
"""
from __future__ import annotations

import collections
import concurrent.futures as cf
import os
import sys
import tempfile

import numpy as np
from PIL import Image

SAMPLES = 12                        # frames the palette is made from
DITHER = 5.0                        # ± levels of the ordered pattern: under a palette step, so flat colours stay flat
BAYER = np.array([[0, 32, 8, 40, 2, 34, 10, 42], [48, 16, 56, 24, 50, 18, 58, 26], [12, 44, 4, 36, 14, 46, 6, 38],
                  [60, 28, 52, 20, 62, 30, 54, 22], [3, 35, 11, 43, 1, 33, 9, 41], [51, 19, 59, 27, 49, 17, 57, 25],
                  [15, 47, 7, 39, 13, 45, 5, 37], [63, 31, 55, 23, 61, 29, 53, 21]], np.float32)
BAYER = np.floor((BAYER / 63.0 - 0.5) * 2 * DITHER).astype(np.int16)      # whole levels: a pixel's level + the pattern, rounded down
WORKERS, AHEAD = max(1, min(6, (os.cpu_count() or 2) - 1)), 8                # threads, and frames in flight at most


def kept_at(i: int, fps: float, out_fps: float) -> bool:
    """Does source frame `i` stay? Evenly spread, the first always."""
    step = out_fps / fps
    return step >= 1 or i == 0 or int(i * step) != int((i - 1) * step)


def delays(keep: list[int], n: int, fps: float) -> list[int]:
    """Each kept frame's length in hundredths of a second: from its time to the next kept frame's (or the end),
    each end rounded on its own so the total is exact."""
    ends = [round(100 * k / fps) for k in keep[1:] + [n]]
    starts = [0] + ends[:-1]
    return [max(1, e - s) for s, e in zip(starts, ends)]


def scaled(raw: bytes, w: int, h: int, ow: int, oh: int) -> np.ndarray:
    im = Image.frombuffer("RGBA", (w, h), raw, "raw", "RGBA", 0, 1)
    if (ow * 2, oh * 2) == (w, h):
        im = im.reduce(2)                       # the half-size box filter, in one fast step
    elif (ow, oh) != (w, h):
        im = im.resize((ow, oh), Image.Resampling.BOX if ow * 2 <= w else Image.Resampling.LANCZOS)
    return np.asarray(im)


def in_order(pool, work, jobs):
    """`work(*job)` for each job on the pool's threads, results in the jobs' order, at most AHEAD in flight."""
    flying = collections.deque()
    for job in jobs:
        flying.append(pool.submit(work, *job))
        if len(flying) >= AHEAD:
            yield flying.popleft().result()
    while flying:
        yield flying.popleft().result()


def palette_of(frames, count: int, see_through: bool) -> Image.Image:
    """One palette image (mode P) from frames spread over the GIF (every pixel of a few, a share of the rest)."""
    picks = np.linspace(0, count - 1, min(SAMPLES, count)).round().astype(int)
    px = []
    for i in dict.fromkeys(picks):
        a = frames(i).reshape(-1, 4)
        a = a[a[:, 3] >= 128][::4]
        px.append(a[:, :3])
    px = np.concatenate(px) if px else np.zeros((1, 3), np.uint8)
    side = int(np.ceil(np.sqrt(len(px))))
    sheet = np.zeros((side * side, 3), np.uint8)
    sheet[:len(px)] = px
    sheet[len(px):] = px[-1]
    return Image.fromarray(sheet.reshape(side, side, 3)).quantize(255 if see_through else 256, Image.Quantize.MEDIANCUT,
                                                                   dither=Image.Dither.NONE)


def paletted(rgba: np.ndarray, pal: Image.Image, see_through: bool) -> Image.Image:
    h, w = rgba.shape[:2]
    pattern = np.tile(BAYER, (-(-h // 8), -(-w // 8)))[:h, :w, None]
    rgb = np.clip(rgba[..., :3].astype(np.int16) + pattern, 0, 255).astype(np.uint8)
    im = Image.fromarray(rgb).quantize(palette=pal, dither=Image.Dither.NONE)
    if see_through:
        idx = np.asarray(im).copy()
        idx[rgba[..., 3] < 128] = 255
        im = Image.fromarray(idx, "P")
    im.putpalette(pal.getpalette()[:765] + [0] * (768 - len(pal.getpalette()[:765])))
    return im


def main(argv: list[str]) -> int:
    out = argv[0]
    w, h = int(argv[1]), int(argv[2])
    fps, ow, oh, ofps = float(argv[3]), int(argv[4]), int(argv[5]), float(argv[6])
    size, stock, seen, see_through, order = ow * oh * 4, tempfile.TemporaryFile(), 0, False, []
    pool = cf.ThreadPoolExecutor(WORKERS)

    def source():                                        # each kept source frame, as it arrives
        nonlocal seen
        while True:
            raw = sys.stdin.buffer.read(w * h * 4)
            if not raw:
                return
            if len(raw) != w * h * 4:
                raise SystemExit(f"gif_encode: frame {seen} ended after {len(raw)} of {w * h * 4} bytes")
            if kept_at(seen, fps, ofps):
                order.append(seen)
                yield raw, w, h, ow, oh
            seen += 1
    for a in in_order(pool, scaled, source()):
        see_through = see_through or bool((a[..., 3] < 128).any())
        stock.write(a.tobytes())
    n = seen
    if not n:
        raise SystemExit("gif_encode: no frames arrived")

    def frame(i):
        stock.seek(i * size)
        return np.frombuffer(stock.read(size), np.uint8).reshape(oh, ow, 4)

    pal = palette_of(frame, len(order), see_through)
    first = paletted(frame(0), pal, see_through)
    tail = in_order(pool, paletted, ((frame(i), pal, see_through) for i in range(1, len(order))))
    opts = {"transparency": 255, "disposal": 2} if see_through else {}
    first.save(out, "GIF", save_all=True, append_images=tail, duration=[10 * d for d in delays(order, n, fps)], loop=0,
               optimize=False, **opts)
    pool.shutdown()
    stock.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
