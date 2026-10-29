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


def test_a_picture_not_made_yet_never_stands_in_with_more_than_is_drawn(tmp_path, monkeypatch):
    """While the screen's in-between pictures are made, each stands in with one drawn less far (or none of it), never
    the whole drawing: the canvas showed the finished painting at 31 % while the export showed only the ink (2D final
    critic). Once made, the screen's entries are the export's."""
    monkeypatch.setenv("ROSTRUM_CACHE_DIR", str(tmp_path))
    from rostrum_core import cache
    monkeypatch.setattr(cache, "CACHE", cache.Cache())
    monkeypatch.setattr(write_on, "CACHE", cache.CACHE)
    f = frame()
    f["paints"][0]["strokes"][0]["color"] = "#123456"          # a drawing of its own (no picture made by another test)
    d = {"id": "d", "type": "drawing", "w": W, "h": H, "frames": [f],
         "keys": [{"prop": "drawnSoFar", "t": 0.0, "v": 0.0}, {"prop": "drawnSoFar", "t": 0.4, "v": 1.0}]}
    later = []
    scene._pictures(d, 10, {"until": 1.0, "later": later})
    for job in [j for j in later if not getattr(j, "ahead", False)]:
        job()
    whole = scene._pictures(d, 10, {"until": 1.0, "later": []})[-1]["src"]
    later = []
    shown = scene._pictures(d, 10, {"until": 1.0, "later": later})
    assert later and all(e["src"] != whole for e in shown[:-1])      # nothing made yet: none of it, not the whole
    min(later, key=lambda j: abs(j.at - 0.1))()                       # the picture at 0.1 s is made
    later = []
    shown = scene._pictures(d, 10, {"until": 1.0, "later": later})
    at = {e["at"]: e["src"] for e in shown}
    assert at[2] == at[1] != whole                                    # 0.2 s stands in with 0.1 s's (drawn less far)
    for job in later:
        job()
    assert scene._pictures(d, 10, {"until": 1.0, "later": []}) == scene._pictures(d, 10, {"until": 1.0})


def test_a_look_makes_only_the_pictures_of_the_frames_it_draws(tmp_path, monkeypatch):
    """warm.scene's `times`: a look at a few moments makes the Drawn so far pictures shown at those frames, not every
    frame's (a run_script look at 2 moments of the Night Market film made ~600, ~80 s); what it draws is the export's."""
    monkeypatch.setenv("ROSTRUM_CACHE_DIR", str(tmp_path))
    from rostrum_core import cache
    monkeypatch.setattr(cache, "CACHE", cache.Cache())
    monkeypatch.setattr(write_on, "CACHE", cache.CACHE)
    f = frame()
    f["paints"][0]["strokes"][0]["color"] = "#654321"          # a drawing of its own (no picture made by another test)
    d = {"id": "d", "type": "drawing", "w": W, "h": H, "frames": [f],
         "keys": [{"prop": "drawnSoFar", "t": 0.0, "v": 0.0}, {"prop": "drawnSoFar", "t": 0.6, "v": 1.0}]}
    later = []
    scene._pictures(d, 10, {"until": 1.0, "later": later})
    pics = [j for j in later if isinstance(j, write_on.Ahead)]
    assert [j.covers for j in pics] == [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6)]    # each from its frame to the next's
    assert set(write_on.wanted(later, {3})) == {j for j in later if not isinstance(j, write_on.Ahead)} | {pics[2]}
    for job in write_on.wanted(later, {3}):
        job()
    looked = {e["at"]: e["src"] for e in scene._pictures(d, 10, {"until": 1.0, "later": []})}
    exported = {e["at"]: e["src"] for e in scene._pictures(d, 10, {"until": 1.0})}
    assert looked[3] == exported[3] and looked[4] != exported[4]     # the frame drawn is the export's; others wait


def test_a_repeat_look_keeps_the_painted_description_until_its_pictures_are_made(tmp_path, monkeypatch):
    """scene_keep: a drawing with pictures still to make is kept (its jobs listed again), so a repeat look reuses it
    (re-described on every look before: ~1-1.6 s on the Night Market film); once a look made one (`ran`), it is
    described again and equals a fresh description."""
    monkeypatch.setenv("ROSTRUM_CACHE_DIR", str(tmp_path))
    from rostrum_core import cache
    from rostrum2d.scene_keep import Keeper
    monkeypatch.setattr(cache, "CACHE", cache.Cache())
    monkeypatch.setattr(write_on, "CACHE", cache.CACHE)
    f = frame()
    f["paints"][0]["strokes"][0]["color"] = "#123456"          # a drawing of its own (no picture made by another test)
    d = {"id": "d", "type": "drawing", "w": W, "h": H, "frames": [f],
         "keys": [{"prop": "drawnSoFar", "t": 0.0, "v": 0.0}, {"prop": "drawnSoFar", "t": 0.6, "v": 1.0}]}
    data = {"comps": [{"id": "c", "type": "comp", "width": W, "height": H, "fps": 10, "duration": 1.0, "layers": [d]}]}
    keeper, args = Keeper(), (data, "c", {}, None, (0.0, 1.0))
    first: list = []
    keeper.describe(*args, later=first)
    again: list = []
    keeper.describe(*args, later=again)
    assert first and keeper.made == 0 and again == first        # kept, and its pictures still said to be made
    job = [next(j for j in again if isinstance(j, write_on.Ahead))]     # a look at the frame it shows makes it
    for j in job:
        j()
    keeper.ran(job)
    looked = keeper.describe(*args, later=[])
    assert keeper.made > 0 and looked == scene.describe(*args, later=[])
