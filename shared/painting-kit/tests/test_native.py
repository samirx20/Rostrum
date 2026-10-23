"""The native stamper lays the same pixels as numpy, bit for bit: what keeps the replay and the pixel cache exact
when one machine has it and another doesn't. Every tip in every mode, wet with and without pick-up, grain, a mask,
a stroke off the edge, the stroke shaping, tip pictures, even spacing and a picture paper."""
import numpy as np
import pytest

from rostrum_paint import brush as B, compose, marks, native, pictures

pytestmark = pytest.mark.skipif(not native.available(), reason="the native stamper is not built (apps/2d/engine/stamp)")
H, W = 120, 200


def test_native_dabs_equal_numpy():
    rng = np.random.default_rng(0)
    base = (rng.random((H, W, 4)) * 0.6).astype(np.float32)
    base[..., :3] = np.minimum(base[..., :3], base[..., 3:])
    under = np.ascontiguousarray(rng.random((H, W, 4)), np.float32)[..., :3]
    ours, theirs = base.copy(), base.copy()
    mask = compose.mask_array({"points": [[20, 10], [190, 30], [120, 115]], "feather": 2, "invert": False}, W, H)
    for k, tip in enumerate(marks.TIPS):
        for m, mode in enumerate(marks.MODES):
            s = dict(mode=mode, seed=k * 5 + m, grain=0.4 * (m % 2), wet=0.5 * (k % 2), sample_all=bool(m % 2),
                     hardness=0.2 + 0.15 * m, even=bool(k % 2), texture=pictures.TEXTURES[(k + m) % 6])
            paper = marks.Paper(H, W, picture=pictures.PAPERS[m % 5], scale=0.5 + 0.4 * k)
            if m % 2:   # the stroke shaping (shape.py): steadiness, tilt, taper, jitter
                s.update(steady=0.3, tilt_angle=0.7, tilt_size=0.5, taper_start=1, taper_end=2, size_jitter=0.3,
                         angle_jitter=25)
            pts = [[-10 + 30 * k, 10 + 20 * m, 0.3, 20, -10], [60 + 20 * k, 40 + 15 * m, 1.0, -30, 40],
                   [150 + 12 * k, 20 * m]]
            got = [B.stamp_stroke(layer, pts, (0.8, 0.2 + 0.1 * m, 0.4), 8 + 4 * k, tip, paper=paper, lay=lay,
                                  mask=mask if k == 2 else None, under=under, **s) for layer, lay in
                   ((ours, native.lay), (theirs, B.dabs))]
            assert got[0].bbox == got[1].bbox and got[0].a.tobytes() == got[1].a.tobytes(), f"{tip} {mode}: coverage"
            assert ours.tobytes() == theirs.tobytes(), f"{tip} {mode}: pixels"
