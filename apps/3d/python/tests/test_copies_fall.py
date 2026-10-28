"""A falling copies item is judged copy by copy (sim/copies_fall.py): a staggered stream is not "a pop"."""
from rostrum3d.sim.copies_fall import judge

FRAMES = list(range(0, 120))


def _stream(n=12, every=6, top=1.0):
    """n copies, each hidden at its mouth until frame i*every, then falling from `top` to 0 like a dropped thing."""
    tracks = []
    for i in range(n):
        t0, pts = i * every, []
        for f in FRAMES:
            t = max(0, f - t0) / 24
            pts.append([0.0, max(0.0, top - 4.9 * t * t), 0.0])
        tracks.append(pts)
    return tracks


def test_a_staggered_stream_seen_whole_is_fine():
    facts, text, fix = judge("dice", _stream(), FRAMES, lambda f, p: "in", 24)
    assert not fix, text
    assert facts["copies"]["falling"] == 12 and facts["copies"]["pops"] == 0
    assert "one after another" in text and "pop" not in text
    assert facts["drop"][0] == 0 and facts["drop"][1] > 60


def test_copies_falling_above_the_picture_are_named():
    seen = lambda f, p: "in" if p[1] < 0.15 else "above"  # noqa: E731 - only the last 15 cm of each drop is in view
    facts, text, fix = judge("dice", _stream(), FRAMES, seen, 24)
    assert fix and facts["copies"]["pops"] + facts["copies"]["unseen"] > 3
    assert "sim.start_in_view" in text
