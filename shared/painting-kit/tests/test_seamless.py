"""Seamless (wrap.py): a stroke that leaves a seamless canvas over an edge comes back on the opposite side exactly as
it would have gone on past that edge, so tiles of the canvas meet with no seam; Fill treats the joined edges as one."""
import numpy as np
import pytest

from rostrum_paint import brush as B, fill

H, W = 60, 100


def test_stroke_over_the_edge_comes_back_on_the_other_side():
    pts = [[70, 20, 1.0], [130, 40, 0.6], [150, 70, 1.0]]          # off the right edge, then off the bottom
    seam = np.zeros((H, W, 4), np.float32)
    B.stamp_stroke(seam, pts, (0.2, 0.4, 0.8), 16, "round", wrap=True)
    big = np.zeros((2 * H, 2 * W, 4), np.float32)                    # the same stroke on a canvas big enough to hold it
    B.stamp_stroke(big, pts, (0.2, 0.4, 0.8), 16, "round")
    folded = big[:H, :W] + big[:H, W:] + big[H:, :W] + big[H:, W:]  # its four quarters laid on one tile (they don't meet)
    assert seam[..., 3].max() > 0.9 and big[H:, W:, 3].max() > 0.5   # it did cross both edges
    assert np.abs(seam - folded).max() < 2 / 255


def test_fill_closes_across_the_joined_edge():
    alpha = np.zeros((H, W), np.float32)
    alpha[:, 20:23] = alpha[:, 70:73] = 1                            # two upright lines: the band between them,
    ring = fill.region(alpha, (90, 30), wrap=True)                   # through the edge, is closed when it wraps
    a = fill.coverage(ring, W, H)
    assert a[30, 95] > 0.99 and a[30, 5] > 0.99 and a[30, 45] == 0
    with pytest.raises(fill.NotClosed):
        fill.region(alpha, (90, 30))                                 # not seamless: it runs out to the edge
