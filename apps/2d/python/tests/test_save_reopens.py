"""A script run never saves a 2D document that won't open again (showreel 2026-10-28: a second script's gradient
stops collided with the first's counted ids, were held back, and the gradient was saved with no colours; opening then
replayed that step under the stricter changed-item check and refused the whole document as damaged)."""
import pytest
from rostrum_core import Document, RostrumError, storage

from rostrum2d import KIND, fill_paint, run_source

A = '''
comp("main", duration=3)
r = shape("a_box", w=400, h=300)
r.effect("gradient", id="a_g", style="linear", angle=135, color1="#4FA0FF", color2="#000000")
'''
B = A.replace("a_", "b_")


def _doc(tmp_path):
    (tmp_path / "docs").mkdir()
    d = Document.new(KIND, folder=tmp_path, item="main")
    d.run_script("a.py", run_source(A, "a.py"))
    d.save()
    return d


def _stops(d, layer):
    return [s for s in d.locs()[layer].item.get("stops", [])]


def test_two_scripts_each_with_a_gradient_keep_both_gradients_and_reopen(tmp_path):
    d = _doc(tmp_path)
    report = d.run_script("b.py", run_source(B, "b.py"))
    assert report.held == []
    storage.save(d, document=False)            # a live document appends history; its document file comes later
    again = Document.open(tmp_path, "main", KIND)
    assert len(_stops(again, "a_box")) == 2 and len(_stops(again, "b_box")) == 2


def test_a_run_that_would_leave_a_gradient_with_no_stops_is_refused_in_words(tmp_path):
    d = _doc(tmp_path)
    out, _ = fill_paint.upgrade(run_source(B, "b.py"), KIND.lists)
    taken = [s["id"] for s in _stops(d, "a_box")]
    layer = next(lay for lay in out["comps"][0]["layers"] if lay["id"] == "b_box")
    for s, id_ in zip(layer["stops"], taken):  # the old collision: the same stop ids as script a's
        s["id"] = id_
    seq = d.seq
    with pytest.raises(RostrumError) as err:
        d.run_script("b.py", out)
    assert "nothing was merged" in str(err.value) and "colour stops" in str(err.value)
    assert d.seq == seq
    storage.save(d, document=False)
    Document.open(tmp_path, "main", KIND)


def test_a_file_whose_last_step_left_a_gradient_without_stops_still_opens(tmp_path):
    """Files saved before the fix: the replayed step is checked no harder than opening the whole file."""
    d = _doc(tmp_path)
    out, _ = fill_paint.upgrade(run_source(B, "b.py"), KIND.lists)
    for lay in out["comps"][0]["layers"]:
        if lay["id"] == "b_box":
            lay["stops"] = []
    from rostrum_core.diff import diff
    from rostrum_core import Who
    d.commit(out, diff(d.data, out, KIND.lists), Who.agent("old-build"), "Run b.py (old build)")
    storage.save(d, document=False)
    again = Document.open(tmp_path, "main", KIND)
    assert _stops(again, "b_box") == []
