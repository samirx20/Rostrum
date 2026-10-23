"""How big a GIF will be, measured, not guessed. Two passes over the export's own picture (the engine draws it):
1. which neighbouring GIF frames differ at all: every frame drawn small and compared (up to CHECKS pairs, spread at
   random with a fixed seed beyond that). A held drawing or a still part costs nothing in a GIF (Pillow merges a frame
   that did not change), so this share is most of the answer, and evenly spaced samples miss it (pictures held on
   twos or threes line up with the spacing);
2. what one changed frame costs: up to PAIRS changed pairs drawn at full size, scaled and turned into palette pictures
   by gif_encode.py's own steps and written by the same writer (only the changed rectangle is written).
The file is then the first frame's cost plus changed frames × their average cost. Lands within ~1.2× of the real file
on a held-drawing loop and a full-frame moving gradient (a flat bytes-per-pixel rule was 100× off on a still loop)."""
from __future__ import annotations

import hashlib
import io

import numpy as np
from PIL import Image

from . import formats, gif_encode

PAIRS = 8                       # changed neighbouring pairs measured at full size
CHECKS = 600                    # neighbouring pairs compared, drawn small (~3 ms a frame)


def _gif(frames: list[Image.Image], see_through: bool) -> int:
    buf = io.BytesIO()
    opts = {"transparency": 255, "disposal": 2} if see_through else {}
    frames[0].save(buf, "GIF", save_all=True, append_images=frames[1:], duration=[70] * len(frames), loop=0,
                   optimize=False, **opts)
    return buf.tell()


def _rgba(view, w: int, h: int, stride: int, alpha: bool) -> np.ndarray:
    a = np.frombuffer(view, np.uint8).reshape(h, stride)[:, :w * 4].reshape(h, w, 4).copy()
    if not alpha and a[..., 3].min() < 255:             # no transparency: over black, opaque (what the export sends)
        a[..., :3] = (a[..., :3].astype(np.uint16) * a[..., 3:] // 255).astype(np.uint8)
        a[..., 3] = 255
    return a


def _differs(eng, times: list[float], n: int) -> tuple[list[int], float]:
    """(changed pair starts among those checked, the share of pairs that changed): frames drawn at a quarter size,
    without motion blur, compared by a hash of their pixels."""
    starts = range(n - 1) if n - 1 <= CHECKS else sorted(np.random.default_rng(0).choice(n - 1, CHECKS, replace=False))
    seen: dict[int, bytes] = {}

    def look(j):
        if j not in seen:
            view, *_ = eng.pixels(times[j], samples=1, scale=0.25)
            seen[j] = hashlib.blake2b(view, digest_size=16).digest()
            del view                                    # (the engine's frame memory can't close while it is held)
        return seen[j]
    changed = [j for j in starts if look(j) != look(j + 1)]
    return changed, len(changed) / max(1, len(starts))


def estimate(eng, start: float, end: float, alpha: bool, size: str, rate: str) -> int:
    """About how many bytes the GIF of the engine's loaded scene (seconds start..end) will be, at the chosen size
    and rate. `eng`: a running engine with the scene loaded (Engine.load)."""
    p = eng.scene["comp"]["props"]
    w, h, fps = p["width"], p["height"], p["fps"]
    count = max(1, round((end - start) * fps))
    ow, oh, ofps, _ = formats.gif_shape(w, h, fps, count, size, rate)
    times = [start + i / fps for i in range(count) if gif_encode.kept_at(i, fps, ofps)]
    n = len(times)
    changed, share = _differs(eng, times, n) if n > 1 else ([], 0.0)
    starts = sorted({changed[round(i)] for i in np.linspace(0, len(changed) - 1, min(PAIRS, len(changed)))}) if changed else []
    picks = sorted({0} | {j for s in starts for j in (s, s + 1)})
    drawn = {}
    for j in picks:
        view, fw, fh, stride = eng.pixels(times[j])
        a = _rgba(view, fw, fh, stride, alpha)
        del view
        drawn[j] = gif_encode.scaled(a.tobytes(), fw, fh, ow, oh)
    see_through = alpha and any(bool((a[..., 3] < 128).any()) for a in drawn.values())
    pal = gif_encode.palette_of(lambda i: drawn[picks[i]], len(picks), see_through)
    shown = {j: gif_encode.paletted(a, pal, see_through) for j, a in drawn.items()}
    first = _gif([shown[0]], see_through)
    if not starts:
        return first
    steps = [_gif([shown[s], shown[s + 1]], see_through) - _gif([shown[s]], see_through) for s in starts]
    return round(first + max(0.0, float(np.mean(steps))) * share * (n - 1))
