"""A live preview (Stagger, any popover or drag) is never saved as if kept (2D critic r8 must-fix 3: closing the window
with Stagger open saved the stagger with no history step). A save while it is open writes what the history leaves; the
window's close cancels it first (Document.drop_gesture), and reopening gives the song its history says."""
import json

from rostrum_core import Document, Who, live

from rostrum2d import KIND, run_source

SRC = '''
comp("intro", duration=3)
for n in range(6):
    shape(f"s{n}", shape="rect", w=40, h=40)
'''
SAM = Who.person("sam")


def _starts(doc):
    return [l.get("start", 0.0) for l in doc.data["comps"][0]["layers"] if l["type"] != "camera"]


def test_closing_with_stagger_open_saves_no_stagger_and_the_song_equals_its_history(tmp_path):
    doc = Document.new(KIND, folder=str(tmp_path), item="main")
    doc.run_script("intro.py", run_source(SRC, "intro.py"))
    doc.save()
    live.keep(doc)
    seq, before = doc.seq, _starts(doc)
    ids = [l["id"] for l in doc.data["comps"][0]["layers"] if l["type"] != "camera"]
    g = doc.gesture("Stagger 6 layers", SAM).__enter__()        # the Stagger panel open, its spread showing
    g.preview([{"op": "layer.stagger", "target": ids, "args": {"by": 0.08, "order": "stack"}}], fresh=True)
    assert _starts(doc) != before
    doc.save()                                                   # a save while it is open (Save, a timer)
    on_disk = json.loads((tmp_path / "docs" / f"main{KIND.ext}").read_text(encoding="utf-8"))
    assert [l.get("start", 0.0) for l in on_disk["doc"]["comps"][0]["layers"] if l["type"] != "camera"] == before
    doc.drop_gesture()                                           # the window closes (LiveLink.close)
    doc.live.fold(always=False)
    assert _starts(doc) == before and doc.seq == seq
    again = Document.open(tmp_path, "main", KIND)
    assert _starts(again) == before and again.seq == seq and again.data == again.at_step(again.seq)
