"""Send to 2D (rostrum3d/send.py): the 2D layer is out of date by content (a changed scene is, an identical re-run isn't,
a re-send with a new render clears it), and a re-send keeps the same layer and what a person did to it."""
from rostrum_core import Document, Who, live, project
from rostrum2d import KIND as KIND2D, render3d

from rostrum3d import KIND, run_source, send
from rostrum3d.mcp.render import _hashes

SRC = '''
cam = camera("cam", focalLength=50, z=3).aim((0, 0, 0))
mesh("ball", shape="sphere", radius=0.2)
shot("hero", name="Hero 01", camera=cam, fps=24, start=0, end=1)
shot("close", name="Close 02", camera=cam, fps=24, start=0, end=1)
'''
AGENT, SAM = Who.agent("claude"), Who.person("Sam")


def _render(folder, doc, shot):
    """A finished render as render.py writes it (its manifest's source), with one stand-in EXR frame."""
    part = project.begin_render(folder, doc.item_id)
    (part / f"product_{shot}.1001.exr").write_bytes(b"exr")
    return project.finish_render(part, {"kind": "pictures", "frames": {"fps": "24/1"},
                                        "source": {"history_entry": doc.seq, **_hashes(doc.data), "shot": shot}})


def _layers(folder):
    d = Document.open(folder, "piece", KIND2D)
    return [i for i in d.items() if i["type"] == "render3d"]


def test_send_marks_out_of_date_by_content_and_keeps_one_layer(tmp_path):
    doc = Document.new(KIND, tmp_path, "product")
    live.keep(doc)
    doc.run_script("product.py", run_source(SRC, "product.py"), AGENT)
    piece = Document.new(KIND2D, tmp_path, "piece", start=[{"op": "comp.add", "args": {"id": "main", "width": 1280, "height": 720}}])
    piece.save()

    _render(tmp_path, doc, "hero")
    _render(tmp_path, doc, "close")                      # a later render of another shot must not replace Hero 01
    out = send.send_shot(tmp_path, doc, "hero", "2d", None, AGENT)
    layer, = _layers(tmp_path)
    assert out["link"]["made"] and layer["shot"] == "hero" and layer["w"] == 1280
    assert render3d.find(layer, tmp_path)["version"] == 1
    assert not render3d.status(layer, tmp_path)["stale"]

    doc.run_script("product.py", run_source(SRC, "product.py"), AGENT)      # an identical re-run: not out of date
    assert not render3d.status(layer, tmp_path)["stale"]
    doc.apply([{"op": "mesh.set", "target": ["ball"], "args": {"radius": 0.3}}], SAM)
    assert render3d.status(layer, tmp_path)["stale"]                        # the scene changed: out of date

    p2 = Document.open(tmp_path, "piece", KIND2D)                          # a person moves the layer in 2D
    p2.apply([{"op": "render3d.set", "target": [layer["id"]], "args": {"x": 100.0}}], SAM)
    p2.save()
    _render(tmp_path, doc, "hero")
    out = send.send_shot(tmp_path, doc, "hero", "2d", None, AGENT)       # re-send: the same layer, current again
    again, = _layers(tmp_path)
    assert not out["link"]["made"] and again["id"] == layer["id"] and again["x"] == 100.0
    assert render3d.find(again, tmp_path)["version"] == 3
    assert not render3d.status(again, tmp_path)["stale"]
