"""A big amounts step planned on a worker thread (rostrum_gui/plan_aside.py: Repeat x4 on a whole song) keeps exactly
what the same step planned at once keeps; a newer step makes an older one void, the same one asked again keeps its plan; Esc's drop leaves the song as before."""
import copy
import time

from PySide6.QtCore import QCoreApplication
from rostrum_core import Document, Who
from rostrum_core.storage import doc_hash
from rostrum_gui.app import qt_app
from rostrum_gui.edits import Drag
from rostrum_gui.plan_aside import PlanAside

from rostrum_sound import KIND, run_source

P = Who.person()
SONG = """
tempo(120)
a = track("a", synth="saw")
for n in range(120):
    a.note(["C4", "E4", "G4"][n % 3], at=beat(n * 0.5), dur=beats(0.5), vel=0.6)
d = track("d", kit="drums")
for b in range(60):
    d.hit("kick" if b % 2 == 0 else "snare", at=beat(b))
"""


def _song():
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"))
    return doc


def _calls(doc, times):
    by = {k: [i["id"] for t in doc.data["tracks"] for i in t.get(k + "s", [])] for k in ("note", "hit")}
    return [{"op": f"{k}.duplicate", "target": ids, "args": {"times": times}} for k, ids in by.items()]


def _land(aside):
    t = time.monotonic()
    while aside.busy and time.monotonic() - t < 20:
        QCoreApplication.processEvents()
        time.sleep(0.005)
    assert not aside.busy, "the plan never landed"


def test_planned_aside_keeps_what_planned_at_once_keeps():
    qt_app()
    at_once, aside_doc = _song(), _song()
    before = copy.deepcopy(aside_doc.data)
    d = Drag(at_once, P, "Repeat")
    d.preview(_calls(at_once, 4), fresh=True)
    d.end()
    aside, said = PlanAside(), []
    d = Drag(aside_doc, P, "Repeat")
    aside.start(d, d.fresh_calls(_calls(aside_doc, 2)), said.append)
    aside.start(d, d.fresh_calls(_calls(aside_doc, 4)), said.append)      # newer: the first is void
    gen = aside._gen
    aside.start(d, d.fresh_calls(_calls(aside_doc, 4)), said.append)      # the same asked again: that plan goes on
    assert aside._gen == gen
    _land(aside)
    assert said == [None]
    d.end()
    assert doc_hash(aside_doc.data) == doc_hash(at_once.data)
    assert len(aside_doc.item("a")["notes"]) == 600
    aside_doc.undo(P)
    assert doc_hash(aside_doc.data) == doc_hash(before)


def test_dropped_plan_leaves_the_song_as_it_was():
    qt_app()
    doc = _song()
    before = doc_hash(doc.data)
    aside, said = PlanAside(), []
    d = Drag(doc, P, "Repeat")
    aside.start(d, d.fresh_calls(_calls(doc, 4)), said.append)
    aside.drop()
    d.end(cancel=True)
    t = time.monotonic()
    while time.monotonic() - t < 1:
        QCoreApplication.processEvents()
    assert said == [] and doc_hash(doc.data) == before and not doc.history.changes[-1:] or \
        doc.history.changes[-1].label != "Repeat"
