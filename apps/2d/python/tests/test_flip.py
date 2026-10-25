"""layer.flip mirrors the picked layers as one picture (positions across the box's centre, Stretch below 0), and a
negative Stretch survives save and load (nothing clamps it)."""
from rostrum_core import Document, Who

from rostrum2d import KIND, run_source

SRC = '''
comp("c", width=640, height=360, duration=1)
shape("a", w=40, h=40, x=100, y=100, rotation=30)
shape("b", w=40, h=40, x=300, y=200)
'''


def _doc(folder=None):
    d = Document.new(KIND, folder=folder, item="flip" if folder else None)
    d.run_script("t.py", run_source(SRC, "t.py"))
    return d


def test_flip_across_mirrors_two_layers_across_their_box_centre():
    d = _doc()
    from rostrum2d import boxes
    x0, x1 = min(boxes.box(d.item(i))[0] for i in "ab"), max(boxes.box(d.item(i))[2] for i in "ab")   # the box round both
    d.apply([{"op": "layer.flip", "target": ["a", "b"], "args": {"axis": "across"}}], Who.person("sam"))
    a, b = d.item("a"), d.item("b")
    assert abs(a["x"] - (x0 + x1 - 100)) < 0.01 and abs(b["x"] - (x0 + x1 - 300)) < 0.01   # (fields keep 0.01 px)
    assert (a["scaleX"], b["scaleX"], a["rotation"], a["y"]) == (-1, -1, -30, 100)
    assert len(d.history.changes) == 2                                  # the script run, then the flip: one change


def test_a_negative_stretch_survives_save_and_load(tmp_path):
    d = _doc(tmp_path)
    d.apply([{"op": "value.set", "target": ["b"], "args": {"prop": "scaleX", "v": -1}}], Who.person("sam"))
    d.save()
    assert Document.open(tmp_path, "flip", KIND).item("b")["scaleX"] == -1
