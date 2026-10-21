"""Does the quick raster line up with Cycles? Phase-correlates edge images of our flat view and a
real Cycles render in a few landmark windows and prints the offset (frame px) of each.

  python check_align.py CYCLES.png [--checker] [--out side_by_side.png]

--checker: the Cycles render shows _checker.png on every surface (paint/guides/where_checker_render.png).
Offsets are 'Cycles minus ours': +x = Cycles is further right. |offset| < 1 px = lined up.
"""
import argparse, os, sys
import numpy as np
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scene, tex, view  # noqa: E402
from gbuffer import GBuffer  # noqa: E402

WINDOWS = {  # frame px (x, y, w, h)
    "jug body + handle": (180, 0, 640, 720), "bowl": (860, 380, 900, 480),
    "front pear": (700, 640, 440, 400), "back pears": (1040, 270, 540, 360),
    "cloth front edge": (480, 780, 1440, 300), "table left": (0, 700, 480, 380)}


def edges(a):
    g = a.mean(-1) if a.ndim == 3 else a
    gx = np.zeros_like(g); gy = np.zeros_like(g)
    gx[:, 1:-1] = g[:, 2:] - g[:, :-2]; gy[1:-1] = g[2:] - g[:-2]
    return np.hypot(gx, gy)


def phase_shift(a, b):
    """Shift d such that b(x) ~ a(x - d), subpixel (parabolic peak)."""
    win = np.outer(np.hanning(a.shape[0]), np.hanning(a.shape[1]))
    A, B = np.fft.fft2((a - a.mean()) * win), np.fft.fft2((b - b.mean()) * win)
    r = np.fft.ifft2(B * np.conj(A) / np.maximum(np.abs(B * np.conj(A)), 1e-9)).real
    py, px = np.unravel_index(np.argmax(r), r.shape)
    def sub(m, p, n):
        c, l, rr = m(p), m((p - 1) % n), m((p + 1) % n)
        den = l - 2 * c + rr
        return p + (0.5 * (l - rr) / den if den != 0 else 0)
    dy = sub(lambda k: r[k, px], py, r.shape[0]); dx = sub(lambda k: r[py, k], px, r.shape[1])
    dy = dy - r.shape[0] if dy > r.shape[0] / 2 else dy
    dx = dx - r.shape[1] if dx > r.shape[1] / 2 else dx
    return dx, dy, r.max()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cycles"); ap.add_argument("--checker", action="store_true"); ap.add_argument("--out")
    a = ap.parse_args()
    cy = tex.load(a.cycles)
    H, W = cy.shape[:2]
    g = GBuffer(W)
    ours = view.shade(g, "flat", checker=a.checker)
    s = W / scene.FRAME_W
    ec, eo = edges(cy), edges(ours)
    print(f"Cycles {W}x{H} vs our flat raster; offsets in frame px (Cycles minus ours)")
    for name, (x, y, w, h) in WINDOWS.items():
        sl = (slice(int(y * s), int((y + h) * s)), slice(int(x * s), int((x + w) * s)))
        dx, dy, peak = phase_shift(eo[sl], ec[sl])
        print(f"  {name:18s} dx {dx / s:+6.2f}  dy {dy / s:+6.2f}   (match strength {peak:.2f})")
    if a.out:
        tex.save(a.out, np.concatenate([cy, ours], 1))
        print("side by side ->", os.path.abspath(a.out))


if __name__ == "__main__":
    main()
