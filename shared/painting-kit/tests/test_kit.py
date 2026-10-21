"""The three things agents and people rely on that would break silently: cached pixels equal a full replay, undo of
a stroke batch is exact, and `landed` reports a miss of the right size."""
import numpy as np
import pytest

import rostrum_paint as RP
from rostrum_core import DocKind, Document, Registry, Who
from rostrum_paint import canvas as C, where as W

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
    C.forget()
    assert np.array_equal(C.render(doc.item("c"), *WH).rgba, live)


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
