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


def test_a_grown_drawing_keeps_its_pixels_and_stamps_only_the_new_stroke(monkeypatch):
    """A drawing that grows left / up moves its strokes and paper by whole px (paint_grow.py) and right / down only gets
    bigger: its kept pixels move with it (canvas._grown_from) instead of every stroke being stamped again, and they
    are the pixels a fresh replay makes (a wash that grew at each sweep froze the press for seconds: critic r12)."""
    def stroke(i, dx=0, dy=0, **brush):
        pts = [[40.37 + 30 * k + dx, 50.11 + 12 * i + 6 * np.sin(k) + dy, 0.5 + 0.05 * k] for k in range(9)]
        return ops.build("stroke", f"s{i}", {"points": [[round(x, 2), round(y, 2), p] for x, y, p in pts], "size": 26,
                                             "color": "#406080", "grain": 0.3, **brush})
    wet = dict(brush="bristle", smudge=True, wet=0.35, hardness=0.6)
    old = [stroke(0), stroke(1, **wet), stroke(2, brush="chalk")]
    small = {"id": "d", "paints": [{"id": "p", "mode": "normal", "opacity": 1, "visible": True, "strokes": old}]}
    C.forget()
    C.render(small, 320, 200)
    dx, dy = 64, 32                         # grown left and up (strokes and paper moved), and right too
    moved = [{**s, "points": [[round(p[0] + dx, 2), round(p[1] + dy, 2), *p[2:]] for p in s["points"]]} for s in old]
    grown = {**small, "paperX": dx, "paperY": dy,
             "paints": [{**small["paints"][0], "strokes": moved + [stroke(3, dx, dy, **wet)]}]}
    stamped = []
    real = C.stamp
    monkeypatch.setattr(C, "stamp", lambda *a, **k: stamped.append(a[1]["id"]) or real(*a, **k))
    live = C.render(grown, 320 + dx + 40, 200 + dy).rgba.copy()
    assert stamped == ["s3"]                # only the new stroke
    C.forget()
    fresh = C.render(grown, 320 + dx + 40, 200 + dy).rgba
    assert np.abs(fresh - live).max() < 1 / 255     # the same picture (points rounded to 0.01 px: last-bit floats)


def test_a_mask_made_round_its_shape_is_the_whole_canvas_mask():
    """compose._mask draws only round the shape (and its feather's reach): the same bytes as the whole canvas at 4x,
    or every masked wash would change."""
    from PIL import Image, ImageDraw, ImageFilter
    from rostrum_paint import compose
    rng = np.random.default_rng(3)
    for i in range(40):
        w, h = int(rng.integers(60, 400)), int(rng.integers(60, 300))
        cx, cy, r = rng.uniform(-40, w + 40), rng.uniform(-40, h + 40), rng.uniform(4, 300)
        ang = np.sort(rng.uniform(0, 2 * np.pi, int(rng.integers(3, 12))))
        pts = [[float(cx + r * rng.uniform(0.3, 1) * np.cos(a)), float(cy + r * rng.uniform(0.3, 1) * np.sin(a))] for a in ang]
        mask = {"points": pts, "feather": [0, 0.5, 2.3, 9, 40][i % 5], "invert": i % 7 == 0}
        im = Image.new("L", (w * 4, h * 4), 0)
        ImageDraw.Draw(im).polygon([(x * 4, y * 4) for x, y in pts], fill=255)
        im = im.reduce(4)
        if mask["feather"]:
            im = im.filter(ImageFilter.GaussianBlur(mask["feather"]))
        whole = np.asarray(im, np.float32) / 255
        assert np.array_equal(compose.mask_array(mask, w, h), 1 - whole if mask["invert"] else whole), i


def test_kept_state_box_is_every_set_bit():
    """The box a kept state stores (kept_disk._set_box) covers every pixel with any bit set, -0.0 too: what's outside
    comes back as +0.0."""
    from rostrum_paint import kept_disk
    rng = np.random.default_rng(4)
    for i in range(30):
        h, w = int(rng.integers(1, 40)), int(rng.integers(1, 60))
        px = np.zeros((h, w, 4), np.float32)
        for _ in range(int(rng.integers(0, 4))):
            y, x, c = int(rng.integers(h)), int(rng.integers(w)), int(rng.integers(4))
            px[y, x, c] = rng.choice([-0.0, 1e-45, 0.5])
        assert kept_disk._set_box(px) == kept_disk._box(px.view(np.uint32).any(axis=2)), i


def test_a_fresh_process_goes_on_from_the_state_kept_on_disk(doc, tmp_path, monkeypatch):
    """A layer state kept on disk (kept_disk) gives the pixels a full replay gives, and only the strokes after it
    are stamped."""
    from rostrum_core.cache import Cache
    from rostrum_paint import kept_disk
    monkeypatch.setattr(kept_disk, "CACHE", Cache(tmp_path / "cache"))
    monkeypatch.setattr(kept_disk, "_MISSING", set())
    monkeypatch.setattr(kept_disk, "EVERY", 0.0)
    monkeypatch.setattr(C, "READ_S", 0.0)
    doc.apply(strokes("ink", 5, brush="bristle") + strokes("glaze", 2, y0=80, brush="chalk"), AGENT)
    C.render(doc.item("c"), *WH)
    kept_disk.flush()
    C.forget()                                               # a new process: nothing in memory
    doc.apply(strokes("glaze", 1, y0=130, brush="chalk"), AGENT)
    stamped, real = [], C.stamp
    monkeypatch.setattr(C, "stamp", lambda *a, **k: stamped.append(a[1]["id"]) or real(*a, **k))
    resumed = C.render(doc.item("c"), *WH).rgba.copy()
    assert len(stamped) == 1
    kept_disk.flush()
    C.forget()
    monkeypatch.setattr(kept_disk, "CACHE", Cache(tmp_path / "empty"))
    monkeypatch.setattr(kept_disk, "_MISSING", set())
    assert np.array_equal(C.render(doc.item("c"), *WH).rgba, resumed)


def test_arrays_kept_on_disk_come_back_byte_for_byte(tmp_path, monkeypatch):
    """kept_disk.arrays (Drawn so far's pen order, the paper's tooth) reads back the exact bytes, dtypes and shapes a
    fresh process would make, so a picture made from them is the same picture."""
    from rostrum_core.cache import Cache
    from rostrum_paint import kept_disk, marks
    monkeypatch.setattr(kept_disk, "CACHE", Cache(tmp_path / "cache"))
    monkeypatch.setattr(kept_disk, "_MISSING", set())
    monkeypatch.setattr(kept_disk, "SLOW", 0.0)
    rng = np.random.default_rng(3)
    covers = np.zeros((3, 40, 50), np.uint8)
    covers[:, 10:20, 5:30] = rng.integers(0, 255, (3, 10, 25))           # mostly empty: kept squeezed
    made = {"order": rng.random((40, 50), np.float32) * 300, "covers": covers, "at": np.array([0, 7, 19], np.int64),
            "neg": np.array([-0.0, np.inf], np.float32), "step": np.float64(1.0 / 3)}
    assert kept_disk.arrays("t", ["a"], lambda: made) is made
    kept_disk.flush()
    got = kept_disk.arrays("t", ["a"], lambda: pytest.fail("made again, not read from disk"))
    assert set(got) == set(made)
    for k, a in made.items():
        assert got[k].dtype == a.dtype and got[k].shape == a.shape and got[k].tobytes() == a.tobytes()
    tooth = marks.Paper(60, 90, origin=(7, 3)).fields()                 # made (and kept on disk)
    kept_disk.flush()
    again = marks.Paper(60, 90, origin=(7, 3)).fields()                 # a fresh paper: read back
    assert all(a.dtype == b.dtype and a.tobytes() == b.tobytes() for a, b in zip(tooth, again))
