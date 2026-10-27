"""A stroke laid in pieces while the pen draws it (brush.stamp_stroke's `piece`, what the 2D live ink lays) gives the
pixels of the stroke laid at once: no square block at each piece's ends, no smear starting over. And the straight
RGBA8 picture of a box (native.straight8) is compose.straight8's, byte for byte."""
import numpy as np
import pytest

from rostrum_paint import brush as B, compose, native

H, W = 420, 1000
PTS = [[130 + 45 * i, 210 + 40 * np.sin(i / 5), 0.7 + 0.3 * np.sin(i / 3)] for i in range(16)]   # ~680 px
LAYS = [B.dabs] + ([native.lay] if native.available() else [])


def _laid(tip, size, s, lay, pieces):
    layer = np.zeros((H, W, 4), np.float32)
    layer[150:270] = (0.1, 0.3, 0.5, 1.0)                                    # paint for a wet brush to smear
    carry = B.Carry()
    for k in (range(2, len(PTS) + 1) if pieces else [len(PTS)]):
        B.stamp_stroke(layer, PTS[:k], (0.8, 0.3, 0.2), size, tip, lay=lay, carry=carry, piece=(0, True), seed=3,
                       by_dab=True, **s)
    return layer


@pytest.mark.parametrize("lay", LAYS, ids=lambda f: f.__module__.split(".")[-1])
def test_a_stroke_laid_in_pieces_is_the_stroke_laid_at_once(lay):
    """A piece a point (15 pieces). Round: the same bytes. Wet bristle 260 px: the reservoir goes on from piece to
    piece; the same pixels except where the bristles' ragged start lies (sized as a share of the stroke so far, which
    an open stroke can't know yet: the first ~18 % of it), whose difference the smear carries a brush width on."""
    assert np.array_equal(_laid("round", 60, dict(hardness=0.9, opacity=0.6), lay, True),
                          _laid("round", 60, dict(hardness=0.9, opacity=0.6), lay, False))
    s = dict(hardness=0.6, wet=0.35, color_jitter=0.08, size_pressure=0.5)
    whole, parts = _laid("bristle", 260, s, lay, False), _laid("bristle", 260, s, lay, True)
    past_start = 130 + int(0.18 * 680) + 260
    assert np.abs(whole[:, past_start:] - parts[:, past_start:]).max() < 1 / 255
    assert np.abs(whole - parts).max() > 0.05            # (the start does differ: the check above is not empty)
    if lay is not B.dabs:                                # and native's pieces are numpy's, bit for bit
        assert parts.tobytes() == _laid("bristle", 260, s, B.dabs, True).tobytes()


def test_straight8_box_is_compose_straight8():
    rng = np.random.default_rng(4)
    px = rng.random((60, 90, 4)).astype(np.float32)
    px[..., 3] = rng.choice([0.0, 1e-7, 1e-6, 2e-6, 0.3, 1.0, 1.2, -0.1], (60, 90)).astype(np.float32)
    px[..., :3] *= rng.choice([0.5, 1.0, 1.5], (60, 90, 1)).astype(np.float32) * px[..., 3:]
    out = np.full((70, 100, 4), 9, np.uint8)
    got = native.straight8(px[10:50, 7:80], out=out[3:43, 11:84])          # boxes of bigger arrays, both sides
    assert got.tobytes() == compose.straight8(np.ascontiguousarray(px[10:50, 7:80])).tobytes()
    assert (out[:3] == 9).all() and (out[:, :11] == 9).all()                 # nothing written outside the box
