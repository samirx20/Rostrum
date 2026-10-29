"""render_export refuses a final with open faults (the ones run_script look names), as Sound and 3D do: the file is
kept as <name>.NOT-DONE, and a keep passes only when it quotes the brief stored with brief("...")."""
import pytest
from rostrum_core import Document
from rostrum_core.errors import RostrumError
from rostrum_core.mcp import brief_keep, faults

from rostrum2d.kind import KIND
from rostrum2d.mcp import film_faults
from rostrum2d.script import run_source

SCRIPT = '''brief("A 3 s title card, the word LAUNCH cropped by the right edge on purpose")
comp("main", width=1280, height=720, duration=3)
text("title", body="LAUNCH", size=160, x=1150, y=360)
'''


def _found(tmp_path):
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(SCRIPT, "s.py", doc))
    comp = doc.data["comps"][0]
    found, _ = film_faults.of_export(doc.data, comp, 0, comp["duration"], "render_export")
    film = tmp_path / "Launch.mp4"
    film.write_bytes(b"film")
    return doc.data, found, film


def test_final_with_open_fault_is_refused_and_held_back(tmp_path):
    data, found, film = _found(tmp_path)
    assert found and all(f["fix"] and "change it in the script" not in f["fix"] for f in found)
    assert film_faults.final("mp4", 0, 3, 3) and not film_faults.final("mp4", 0, 2, 3) and not film_faults.final("png", 0, 3, 3)
    with pytest.raises(RostrumError) as e:
        faults.deliver(found, brief_keep.screen(found, None, data), "render_export", film)
    assert "NOT DONE" in str(e.value) and not film.exists() and (tmp_path / "Launch.NOT-DONE.mp4").is_file()


def test_keep_quoting_the_brief_passes_and_an_unquoted_one_is_refused(tmp_path):
    data, found, film = _found(tmp_path)
    loose = {f["id"]: "it looks better this way" for f in found}
    with pytest.raises(RostrumError) as e:
        faults.deliver(found, brief_keep.screen(found, loose, data), "render_export", film)
    assert "keep refused" in str(e.value) and "does not quote the brief" in str(e.value)
    data, found, film = _found(tmp_path)
    quoted = {f["id"]: 'the brief asks for "cropped by the right edge on purpose"' for f in found}
    faults.deliver(found, brief_keep.screen(found, quoted, data), "render_export", film)
    assert film.is_file()
    data, found, film = _found(tmp_path)            # a quote that asks for something else keeps nothing (Undertow r1)
    other = {f["id"]: 'the brief says "A 3 s title card"' for f in found}
    with pytest.raises(RostrumError) as e:
        faults.deliver(found, brief_keep.screen(found, other, data), "render_export", film)
    assert "never asks for a crop at the frame edge" in str(e.value)


def test_scenery_bleeding_off_the_edge_is_advice_a_card_is_a_fault():
    shape_cut = {"kind": "edge_cut", "type": "shape", "start": 0, "end": 10, "id": "reef3", "text": "reef3 cut"}
    card_cut = {**shape_cut, "type": "group", "id": "card"}
    passing = {**card_cut, "end": 1}
    assert [f["id"] for f in film_faults.as_faults([shape_cut, card_cut, passing])] == ["edge_cut:card"]
