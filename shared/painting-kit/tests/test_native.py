"""The native stamper lays the same pixels as numpy, bit for bit: what keeps the replay and the pixel cache exact
when one machine has it and another doesn't. Every tip in every mode, wet with and without pick-up, grain, a mask,
a stroke off the edge, the stroke shaping, tip pictures, even spacing and a picture paper."""
import numpy as np
import pytest

from rostrum_paint import brush as B, compose, marks, native, pictures

needs_native = pytest.mark.skipif(not native.available(), reason="the native stamper is not built (apps/2d/engine/stamp)")
needs_walks = pytest.mark.skipif(not native.walks(), reason="the native stamper is built from before its spacing and fill")
H, W = 120, 200


def test_out_of_date_stamper_refused():
    """A stale build (no layout export, or another layout) is refused with what to rebuild, never called: calling it
    read the arguments wrongly and crashed ("access violation writing 0x0")."""
    class Old:                                        # a build from before layout 3: no rostrum2d_stamp_layout
        pass

    class Other:
        rostrum2d_stamp_layout = staticmethod(lambda: 7.0)

    for lib, built in ((Old(), "2 or older"), (Other(), "7.0")):
        with pytest.raises(native.OutOfDate, match=f"built for layout {built}, this code needs {native.LAYOUT}.*cargo build --profile agent -p "
                                                     f"rostrum2d-stamp"):
            native.check_layout(lib, "x.dll")


@needs_native
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
                     hardness=min(0.95, 0.2 + 0.15 * m), even=bool(k % 2), texture=pictures.TEXTURES[(k + m) % 6])
            paper = marks.Paper(H, W, picture=pictures.PAPERS[m % 5], scale=0.5 + 0.4 * k)
            if m % 2:   # the stroke shaping (shape.py): steadiness, tilt, taper, jitter
                s.update(steady=0.3, tilt_angle=0.7, tilt_size=0.5, taper_start=1, taper_end=2, size_jitter=0.3,
                         angle_jitter=25)
            row = m % 5                                   # every stroke on the canvas
            pts = [[-10 + 30 * k, 10 + 20 * row, 0.3, 20, -10], [60 + 20 * k, 40 + 15 * row, 1.0, -30, 40],
                   [150 + 12 * k, 20 * row]]
            got = [B.stamp_stroke(layer, pts, (0.8, 0.2 + 0.1 * m, 0.4), 8 + 4 * k, tip, paper=paper, lay=lay,
                                  mask=mask if k == 2 else None, under=under, **s) for layer, lay in
                   ((ours, native.lay), (theirs, B.dabs))]
            assert got[0].bbox == got[1].bbox and got[0].a.tobytes() == got[1].a.tobytes(), f"{tip} {mode}: coverage"
            assert ours.tobytes() == theirs.tobytes(), f"{tip} {mode}: pixels"


@needs_native
def test_native_equals_numpy_on_a_seamless_canvas():
    """Wrapping strokes (wrap.py): the parts of every dab, the wet reservoir picking up across the joined edges."""
    rng = np.random.default_rng(1)
    base = (rng.random((H, W, 4)) * 0.6).astype(np.float32)
    base[..., :3] = np.minimum(base[..., :3], base[..., 3:])
    under = np.ascontiguousarray(rng.random((H, W, 4)), np.float32)[..., :3]
    ours, theirs = base.copy(), base.copy()
    paper = marks.Paper(H, W, wrap=True)
    for k, tip in enumerate(marks.TIPS):
        s = dict(seed=k, wrap=True, grain=0.3 * (k % 2), wet=0.6 * (k % 2), sample_all=k == 3, mode=marks.MODES[k])
        pts = [[W - 20 + 3 * k, 10 + 15 * k, 0.5], [W + 40, H - 5 + 4 * k, 1.0], [W + 90, H + 30, 0.8]]
        got = [B.stamp_stroke(layer, pts, (0.7, 0.3, 0.2), 10 + 6 * k, tip, paper=paper, lay=lay, under=under, **s)
               for layer, lay in ((ours, native.lay), (theirs, B.dabs))]
        assert got[0].bbox == got[1].bbox and got[0].a.tobytes() == got[1].a.tobytes(), f"{tip}: coverage"
        assert ours.tobytes() == theirs.tobytes(), f"{tip}: pixels"


@needs_native
def test_native_equals_numpy_for_big_overlapping_dabs():
    """Big brushes take the native stamper's fast paths (several threads, pixels a dab can't change skipped): the
    same pixels still, dry and wet, in the modes that step by their own rounding, with a mask, grain and a tip picture."""
    h, w = 260, 420
    rng = np.random.default_rng(2)
    base = (rng.random((h, w, 4)) * 0.6).astype(np.float32)
    base[..., :3] = np.minimum(base[..., :3], base[..., 3:])
    under = np.ascontiguousarray(rng.random((h, w, 4)), np.float32)[..., :3]
    ours, theirs = base.copy(), base.copy()
    mask = compose.mask_array({"points": [[0, 0], [420, 40], [300, 260], [0, 200]], "feather": 6, "invert": False}, w, h)
    cases = [("round", dict(hardness=1.0)), ("round", dict(hardness=0.3, mode="multiply")),
             ("bristle", dict(wet=0.4, hardness=0.6)), ("round", dict(wet=0.6, sample_all=True, mode="screen")),
             ("chalk", dict(grain=0.5, mode="overlay")), ("flat", dict(texture=pictures.TEXTURES[2])),
             ("block", dict(mode="add")), ("line", dict(mode="erase"))]
    for k, (tip, s) in enumerate(cases):
        pts = [[30, 60 + 15 * k, 0.6], [200, 180 - 10 * k, 1.0], [400, 90 + 12 * k, 0.8]]
        got = [B.stamp_stroke(layer, pts, (0.3, 0.6, 0.2), 140, tip, paper=marks.Paper(h, w), lay=lay, seed=k,
                              mask=mask if k % 3 == 1 else None, under=under, spacing=0.06, **s)
               for layer, lay in ((ours, native.lay), (theirs, B.dabs))]
        assert got[0].a.tobytes() == got[1].a.tobytes(), f"{tip} {s}: coverage"
        assert ours.tobytes() == theirs.tobytes(), f"{tip} {s}: pixels"


@needs_walks
def test_native_spacing_equals_the_python_walk():
    """Where the dabs go (brush._spacing, its taper's shape.step_scale): the native walk gives the same places, number
    for number, on many strokes: flat and changing pressure, size pressure, tapers at either end or both (sized by the
    path or endless, as an open stroke's), short and long paths, paths with repeated points."""
    rng = np.random.default_rng(7)
    for i in range(400):
        n = int(rng.integers(1, 60))
        steps = rng.random(n - 1) * rng.choice([0.5, 5, 40]) * (rng.random(n - 1) > 0.1)     # some points repeat
        L = np.concatenate([[0.0], np.cumsum(steps)])
        pr = np.full(n, 0.7) if i % 4 == 0 else rng.random(n)
        size = float(rng.choice([1, 3, 8.5, 24, 120]))
        p = {"taper_start": float(rng.choice([0, 0, 0.5, 2])), "taper_end": float(rng.choice([0, 0.7, 3])),
             "size_jitter": 0}
        step, sp = float(rng.choice([0.3, 0.9, 2.5, 11.0])), float(rng.choice([0, 0.5, 0.8, 1]))
        length = None if i % 3 else float("inf")
        want = B._spacing(L, pr, step, sp, size, p, length)
        got = B.spaced(L, pr, step, sp, size, p, length)
        assert np.asarray(want, np.float64).tobytes() == np.asarray(got, np.float64).tobytes(), f"stroke {i}"


@needs_walks
def test_native_fill_equals_apply_paint():
    """A fill's paint (fill.lay): the native pass lays marks.apply_paint's numbers, normal from no coverage, into a
    box of a bigger layer."""
    rng = np.random.default_rng(3)
    base = (rng.random((H, W, 4)) * 0.8).astype(np.float32)
    base[..., :3] = np.minimum(base[..., :3], base[..., 3:])
    c = (rng.random((50, 70)) * (rng.random((50, 70)) > 0.3)).astype(np.float32)
    c[0, :5] = [0, 1, 0.5, 1e-7, 0.9999]
    for col in ((0.2, 0.9, 0.31), (1.0, 0.0, 1 / 3)):
        col = np.asarray(col, np.float32)
        ours, theirs = base.copy(), base.copy()
        native.fill(ours[13:63, 21:91], c, col)
        marks.apply_paint(theirs[13:63, 21:91], np.zeros_like(c), c, col, "normal")
        assert ours.tobytes() == theirs.tobytes()
