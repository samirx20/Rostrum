"""The things agents and people rely on that would break silently: cached pixels equal a full replay, undo of
a stroke batch is exact, `landed` reports a miss of the right size, and a script re-run removes the strokes it no
longer makes but never a stroke a person changed."""
import numpy as np
import pytest

import rostrum_paint as RP
from rostrum_core import DocKind, Document, Registry, Who
from rostrum_paint import canvas as C, ops, where as W

REG = Registry()
RP.register(REG, ("canvas",))
KIND = DocKind("painttest", ".pt", REG, lists={"doc": ["canvases"], "canvas": RP.CANVAS_LISTS, **RP.LISTS})
WH = (320, 200)
AGENT = Who.agent("painter")


@pytest.fixture
def doc():
    d = Document.new(KIND)
    d.data["canvases"] = [{"id": "c", "type": "canvas", "paints": [], "paintmasks": []}]
    d.apply([{"op": "paint.add", "target": "c", "args": {"id": "ink"}},
             {"op": "paint.add", "target": "c", "args": {"id": "glaze", "mode": "multiply", "opacity": 0.7}}], AGENT)
    return d


def strokes(layer, n, y0=40, **brush):
    return [{"op": "stroke.add", "target": layer, "args": {
        "points": [[20 + 30 * i, y0 + 10 * j + 8 * np.sin(i + j), 0.4 + 0.06 * i] for i in range(9)],
        "size": 14, "color": "#%02x6040" % (40 + 20 * j), **brush}} for j in range(n)]


def test_cached_pixels_equal_full_replay(doc):
    for batch in (strokes("ink", 6, brush="bristle"), strokes("glaze", 3, y0=80, brush="chalk", grain=0.4),
                  strokes("ink", 2, y0=120, smudge=True, wet=0.6, pickup=True)):
        doc.apply(batch, AGENT)
        live = C.render(doc.item("c"), *WH).rgba.copy()      # each look stamps only the new strokes
    key = C.content_key(doc.item("c"), *WH)                  # each look keys only the new strokes, too
    C.forget()
    assert C.content_key(doc.item("c"), *WH) == key
    assert np.array_equal(C.render(doc.item("c"), *WH).rgba, live)


def test_one_dab_taper_step_equals_the_taper():
    """brush.plan asks shape.step_scale once per dab (worked out with math); it must be shape.taper's number exactly,
    or a stroke's dabs would move."""
    from rostrum_paint import shape
    rng = np.random.default_rng(5)
    for _ in range(2000):
        L, size, start, end = rng.uniform(1, 2000), rng.uniform(1, 120), rng.choice([0, 0.4, 2]), rng.choice([0, 1, 3])
        t = rng.uniform(0, L)
        if start or end:
            assert shape.step_scale(t, L, size, {"taper_start": start, "taper_end": end}) ==                 float(shape.taper(np.array([t]), L, size, start, end)[0])


def test_undo_of_a_batch_is_exact(doc):
    doc.apply(strokes("ink", 4), AGENT)
    before_data, before_px = doc.data["canvases"], C.render(doc.item("c"), *WH).rgba.copy()
    change = doc.apply(strokes("ink", 5, y0=90) + strokes("glaze", 2), AGENT)
    assert len(change.edits) == 7 and change.who == AGENT    # one batch = one change, with who painted it
    C.render(doc.item("c"), *WH)
    C._SEEN.clear()                                          # undo must rebuild from kept states, not a memo
    doc.undo(AGENT)
    assert doc.data["canvases"] == before_data
    assert np.array_equal(C.render(doc.item("c"), *WH).rgba, before_px)


def test_landed_reports_the_miss(doc):
    doc.apply({"op": "stroke.add", "target": "ink",
               "args": {"id": "s", "points": [[30, 100], [290, 100]], "size": 12, "brush": "round"}}, AGENT)
    assert W.landed(doc.item("c"), *WH, "s")["landed"]
    r = W.landed(doc.item("c"), *WH, "s", path=[[30, 106], [290, 106]])
    assert not r["landed"] and r["mean"] == pytest.approx(6, abs=0.5)


def painted_by_script(*stroke_ids):
    """What a painting script outputs: one canvas, one paint layer, the strokes it makes this run (built by the
    kit's one builder, as an app's script layer does)."""
    out = KIND.blank()
    paint = ops.build("paint", "ink", {})
    paint["strokes"] = [ops.build("stroke", s, {"points": [[20, 30 + 40 * n], [300, 30 + 40 * n]], "size": 10})
                        for n, s in enumerate(stroke_ids)]
    out["canvases"] = [{"id": "c", "type": "canvas", "paints": [paint], "paintmasks": []}]
    return out


def test_script_rerun_removes_its_dropped_strokes_but_keeps_a_persons_edit():
    d = Document.new(KIND)
    d.run_script("strokes.py", painted_by_script("s1", "s2", "s3"))
    d.apply({"op": "stroke.set", "target": "s2", "args": {"color": "#ff0000"}}, Who.person("sam"))
    report = d.run_script("strokes.py", painted_by_script("s3"))      # the new run no longer makes s1 or s2
    left = [s["id"] for s in d.item("ink")["strokes"]]
    assert "s1" not in left                                             # the script's own stroke goes
    assert "s2" in left and d.item("s2")["color"] == "#ff0000"          # the person's stroke stays, as they left it
    assert [h["key"] for h in report.held] == ["s2"]                    # and the script says it kept it
    assert C.render(d.item("c"), *WH).order == left                     # the pixels follow the document
