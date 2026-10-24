"""Painting on a mesh (SPEC §5): the unfolded surface, paint layers (each painting one channel) and their strokes survive
save and reopen; a stroke, even one split in two at a seam, is one undo step. The unfold comes from a stand-in for
the engine (mesh.unfold stores whatever the core answers)."""
from rostrum_core import Document, Who

from rostrum3d import KIND, run_source, unfold

SAM = Who.person()
SRC = '''
mesh("lid", shape="cylinder", radius=0.03, height=0.01)
cam = camera("cam", z=0.4)
shot("hero", camera=cam, fps=24, start=0, end=1)
'''
UVS = [0.25, 0.75] * 6


def _lid(tmp_path):
    unfold.use_unfold(lambda doc, id_, size: {"uvs": UVS, "charts": 1, "used": 0.5})
    d = Document.new(KIND, folder=tmp_path, item="scene")
    d.run_script("lid.py", run_source(SRC, "lid.py"))
    d.apply({"op": "mesh.unfold", "target": ["lid"]}, SAM)
    d.apply({"op": "paint.add", "target": ["lid"], "args": {"id": "scuffs", "name": "Scuffs", "channel": "roughness"}}, SAM)
    return d


def test_paint_survives_save_and_reopen(tmp_path):
    d = _lid(tmp_path)
    d.apply({"op": "stroke.add", "target": ["scuffs"], "args": {"points": [[100, 100, 1], [400, 300, 0.5]], "color": "#b0b0b0",
                                                                 "size": 40, "brush": "chalk"}}, SAM)
    d.save()
    again = Document.open(tmp_path, "scene", KIND)
    lid = again.item("lid")
    assert lid["uvs"] == UVS and lid["paintSize"] == 2048
    assert [(p["id"], p["channel"]) for p in lid["paints"]] == [("scuffs", "roughness")]
    assert lid["paints"][0]["strokes"] == d.item("lid")["paints"][0]["strokes"]
    assert not KIND.check(again.data)


def test_a_stroke_is_one_undo_step(tmp_path):
    d = _lid(tmp_path)
    split = [{"op": "stroke.add", "target": ["scuffs"], "args": {"points": pts, "color": "#ffffff", "size": 24}}
             for pts in ([[10, 10], [60, 20]], [[1500, 900], [1550, 950]])]      # one drag, cut in two at a seam
    d.apply(split, SAM, label="Paint on Lid")
    assert len(d.item("scuffs")["strokes"]) == 2
    d.undo(SAM)
    assert d.item("scuffs")["strokes"] == [] and d.item("lid")["uvs"] == UVS     # the layer and the unfold stay
