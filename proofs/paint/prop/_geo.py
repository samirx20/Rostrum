# Shared placement helpers for the jug stroke scripts (frame pixels, 1920x1080).
# The scripts run inside the kit (`paint.py run`), which gives them `doc`; they do `from _geo import *`.
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, "..", "kit")))
from brush import curve  # noqa: E402,F401

SIL = json.load(open(os.path.join(HERE, "silhouette.json")))
JUG, HANDLE = SIL["Jug"]["polygon"], SIL["JugHandle"]["polygon"]
# centre line of the handle in frame px, read off a zoomed view (top bar, then down the C)
HANDLE_PATH = [(366, 150), (300, 149), (252, 163), (222, 205), (210, 280), (216, 360), (246, 430), (292, 476),
               (348, 518)]
HANDLE_STRIPE = HANDLE_PATH


def edges(y, poly=JUG):
    """Left and right edge x of the object's row y (nearest outline row)."""
    n = len(poly) // 2
    left, right = poly[:n], poly[n:][::-1]
    i = min(range(n), key=lambda k: abs(left[k][1] - y))
    return left[i][0], right[i][0]


def sag(y):
    """How far a horizontal ring of the jug bows downward at its middle (camera looks down)."""
    return 14 + 30 * max(0.0, y) / 712


def ring(y, t0=0.0, t1=1.0, inset=0, n=24, pressure=(0.6, 1.0, 0.6)):
    """Stroke path around the jug at row y, from t0 to t1 across its width (0 = left edge)."""
    l, r = edges(y)
    l, r = l + inset, r - inset
    pts = []
    for k in range(n + 1):
        t = t0 + (t1 - t0) * k / n
        u = 2 * t - 1
        pts.append((l + (r - l) * t, y + sag(y) * (1 - u * u)))
    lo, mid, hi = pressure
    return [(x, yy, lo + (mid - lo) * (1 - abs(2 * k / n - 1)) if k <= n // 2 else hi + (mid - hi) * (1 - abs(2 * k / n - 1)))
            for k, (x, yy) in enumerate(pts)]


def along_edge(side, y0, y1, offset, n=24, pressure=(0.3, 1.0, 0.3)):
    """Stroke path parallel to the jug's left/right outline, `offset` px inside it."""
    pts = []
    for k in range(n + 1):
        y = y0 + (y1 - y0) * k / n
        l, r = edges(y)
        pts.append((l + offset if side == "left" else r - offset, y))
    return curve(*pts, n=n * 2, pressure=pressure)
