"""A script's new scene arrives with its frame even when the document already holds a frame called "frame" (the guide's
first example, comp("main"), on a project that already has a scene), and a re-run keeps the same ids."""
from rostrum_core import Document, RostrumError
from rostrum2d import KIND, run_source
import pytest

FIRST = 'comp("scene1", width=320, height=180)\nshape("a")\n'
MAIN = 'comp("main", width=640, height=360)\ntext("headline", body="Hi")\n'


def _run(doc, name, src):
    return doc.run_script(name, run_source(src, name, doc))


def _frames(doc, scene):
    return [l["id"] for c in doc.data["comps"] if c["id"] == scene for l in c["layers"] if l["type"] == "camera"]


def test_a_new_scene_from_a_script_gets_its_own_frame_beside_an_existing_one():
    d = Document.new(KIND)
    _run(d, "first.py", FIRST)
    _run(d, "main.py", MAIN)
    assert len(_frames(d, "main")) == 1 and len(_frames(d, "scene1")) == 1
    seq = d.seq
    _run(d, "main.py", MAIN)                            # a re-run: same ids, nothing to change
    assert d.seq == seq and len(_frames(d, "main")) == 1


def test_text_path_that_is_not_path_data_is_refused_with_the_line_to_write():
    d = Document.new(KIND)
    _run(d, "main.py", MAIN)
    with pytest.raises(RostrumError) as e:
        _run(d, "main.py", MAIN.replace('body="Hi"', 'body="Hi", path="trend"'))
    assert "text.follow" in str(e.value)
