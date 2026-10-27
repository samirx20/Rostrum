"""Drawn so far (write_on.py): 0 shows nothing, 100 % the whole drawing, 50 % the first half in drawing order."""
import numpy as np
from rostrum_paint import canvas, ops

from rostrum2d import scene, write_on

W, H = 200, 80


def frame():
    paint = ops.build("paint", "ink", {})            # two strokes as long as each other: the first, then the second
    paint["strokes"] = [ops.build("stroke", f"s{i}", {"points": [[20, y], [180, y]], "size": 12, "brush": "round",
                                                       "color_jitter": 0.0}) for i, y in enumerate((20, 60))]
    return {"id": "f0", "type": "frame", "at": 0, "paints": [paint], "paintmasks": []}


def test_the_amount_reveals_the_strokes_in_drawing_order_with_a_round_head():
    f = frame()
    assert write_on.pixels(f, W, H, 0.0)[..., 3].max() == 0
    assert np.array_equal(write_on.pixels(f, W, H, 1.0), canvas.rgba8(f, W, H))
    half = write_on.pixels(f, W, H, 0.5)
    assert np.array_equal(half[:40], canvas.rgba8(f, W, H)[:40])        # the first stroke whole
    assert half[40:, :, 3].max() == 0                                    # the second not begun
    quarter = write_on.pixels(f, W, H, 0.25)                             # the pen half way along the first
    a = quarter[..., 3]
    assert a[20, 40] > 200 and a[20, 160] == 0
    ahead = np.flatnonzero(a[20] > 0).max()
    assert 95 <= ahead <= 115 and a[14, ahead] == 0                      # its head ends round, not cut straight


def test_a_keyed_amount_sends_a_picture_per_frame_it_changes():
    d = {"id": "d", "type": "drawing", "w": W, "h": H, "frames": [frame()],
         "keys": [{"prop": "drawnSoFar", "t": 0.0, "v": 0.0}, {"prop": "drawnSoFar", "t": 0.2, "v": 1.0}]}
    shown = scene._pictures(d, 10, {"until": 1.0})
    assert [e["at"] for e in shown] == [0, 1, 2]                         # 0 %, 50 %, then whole and held
    assert len({e["src"] for e in shown}) == 3


def test_the_screen_shows_the_exports_pictures_after_a_stroke_is_added():
    """The screen (`later`: pictures made off its thread) ends on the very entries the export uses, also after an edit;
    a drawing's own picture is asked for once, so it isn't held up behind the in-between ones (2D r12 must-fix 1)."""
    def drawn(f):
        return {"id": "d", "type": "drawing", "w": W, "h": H, "frames": [f],
                "keys": [{"prop": "drawnSoFar", "t": 0.0, "v": 0.0}, {"prop": "drawnSoFar", "t": 0.4, "v": 1.0}]}

    def on_screen(d):
        for _ in range(3):                      # the waits, then the in-between pictures, then nothing left
            later = []
            shown = scene._pictures(d, 10, {"until": 1.0, "later": later})
            waits = [j for j in later if not getattr(j, "ahead", False)]
            assert len(waits) <= 1
            for job in waits or later:
                job()
        assert not later
        return shown

    before = frame()
    assert on_screen(drawn(before)) == scene._pictures(drawn(before), 10, {"until": 1.0})
    after = {**before, "paints": [{**before["paints"][0], "strokes": before["paints"][0]["strokes"] + [
        ops.build("stroke", "s2", {"points": [[20, 40], [180, 40]], "size": 12, "brush": "round", "color_jitter": 0.0})]}]}
    shown = on_screen(drawn(after))
    assert shown == scene._pictures(drawn(after), 10, {"until": 1.0})
    assert shown != on_screen(drawn(before))     # the added stroke makes new pictures at every in-between time
