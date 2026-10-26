"""A script works on the open document: it names markers added with marker.add (one list of markers, the
document's), and a run that fails changes nothing (no stray track that breaks the next run). Both broke silently for
agents in round 3 (piece 2)."""
import copy

import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum_sound import KIND, compile, run_source

from test_script_forms import server

CUE = 'h = track("horns", builtIn="horn")\nh.note("D3", at="#cut to street", dur=1.0)\n'


@pytest.fixture
def doc(tmp_path):
    d = Document.new(KIND, folder=tmp_path, item="cue")
    d.apply([{"op": "marker.add", "args": {"name": "cut to street", "at": 5.0}}], Who.agent("m"))
    return d


def test_a_script_names_a_marker_the_document_has(doc):
    doc.run_script("cue.py", run_source(CUE, "cue.py", doc), Who.agent("m"))
    assert compile(doc)["tracks"][0]["notes"][0]["at"] == 5.0
    assert [m["name"] for m in doc.data["markers"]] == ["cut to street"]       # read, not made a second time


def _unchanged(doc, fn):
    seq, data, bases = doc.seq, copy.deepcopy(doc.data), copy.deepcopy(doc.script_bases)
    with pytest.raises(RostrumError):
        fn()
    assert (doc.seq, doc.data, doc.script_bases) == (seq, data, bases)


def test_a_failed_script_changes_nothing(doc):
    bad = 'h = track("h2", builtIn="horn")\nh.note("D3", at="#cut to street", end=2.0)\n'     # ends before it starts
    _unchanged(doc, lambda: doc.run_script("t2.py", run_source(bad, "t2.py", doc), Who.agent("m")))
    tree = run_source(CUE, "t2.py", doc)
    tree["tracks"][0]["instrument"] = "none"                    # past the script's own check: the merge refuses it whole
    _unchanged(doc, lambda: doc.run_script("t2.py", tree, Who.agent("m")))
    doc.run_script("cue.py", run_source(CUE, "cue.py", doc), Who.agent("m"))     # the next run is not blocked
    assert [t["id"] for t in doc.data["tracks"]] == ["horns"]


def test_a_run_that_merged_never_replies_failed(tmp_path, monkeypatch):
    """A tie a moved marker broke is a warning; the next run merges, and its reply says so (it once failed after
    the change was in, so the agent saw an error for a run that had changed the song)."""
    app, rt = server(tmp_path, monkeypatch)
    try:
        held = 'h = track("h2", builtIn="horn")\nh.note("D3", at="#footsteps", end=12.0)\n'
        rt.call("edit_document", {"ops": [{"op": "marker.add", "args": {"name": "footsteps", "at": 11.2}}]}, Who.agent("m"))
        assert rt.call("run_script", {"name": "t2", "source": held}, Who.agent("m"))[0]["ok"]
        rt.call("edit_document", {"ops": [{"op": "marker.move", "target": ["marker.footsteps"], "args": {"at": 13.0}}]}, Who.agent("m"))
        reply, _ = rt.call("run_script", {"name": "cue", "source": CUE.replace("cut to street", "footsteps")}, Who.agent("m"))
        assert reply["ok"] and app.documents["main"].seq == 4, reply
    finally:
        app.state.engine.close()
