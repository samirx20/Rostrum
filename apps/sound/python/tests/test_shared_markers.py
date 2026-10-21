"""Sound on the project's shared markers (shared/project-service/MARKERS.md): a marker moved elsewhere moves the
sound on the next compile, a rename is followed as one undo step, a deleted used marker and a local/shared name
clash fail loudly. Silent mistakes here would put a cue on the wrong frame."""
import pytest
from rostrum_core import Document, RostrumError, Who
from rostrum_core import markers as project

from rostrum_sound import KIND, compile, run_source
from rostrum_sound.doc import markers, ops_mix

CUE = """
hit = track("hit", builtIn="warmPad")
hit.note("D4", at="#logo lands+0.5", dur=1.0)
"""


def _note_at(doc):
    return compile(doc)["tracks"][0]["notes"][0]["at"]


@pytest.fixture
def doc(tmp_path):
    project.edit(tmp_path, [{"op": "marker.add", "args": {"name": "logo lands", "at": 2.5}}], Who.person())
    d = Document.new(KIND, folder=tmp_path, item="cue")
    with markers.project(tmp_path):
        d.run_script("cue.py", run_source(CUE, "cue.py"), Who.script("cue.py"))
        yield d


def _id(folder):
    return project.listing(folder)[0]["id"]


def test_a_moved_marker_moves_the_sound(doc):
    assert _note_at(doc) == 3.0
    project.edit(doc.folder, [{"op": "marker.move", "target": [_id(doc.folder)], "args": {"at": 4.0}}], Who.person())
    assert _note_at(doc) == 4.5
    assert markers.used(doc.data) == {"logo lands": 4.0}


def test_a_rename_is_followed_as_one_undo_step(doc):
    project.edit(doc.folder, [{"op": "marker.rename", "target": [_id(doc.folder)], "args": {"name": "hit"}}],
                 Who.person())
    calls = ops_mix.follow_calls(doc.data)
    assert calls == [{"op": "marker.follow", "args": {"old": "logo lands", "new": "hit"}}]
    doc.apply(calls, Who.person())          # as the screen does: the person's one step
    assert doc.item("hit")["notes"][0]["at"] == "#hit+0.5" and _note_at(doc) == 3.0
    doc.undo(Who.person())
    assert doc.item("hit")["notes"][0]["at"] == "#logo lands+0.5"


def test_a_deleted_used_marker_fails_loudly(doc):
    project.edit(doc.folder, [{"op": "marker.remove", "target": [_id(doc.folder)]}], Who.person())
    with pytest.raises(RostrumError, match="logo lands"):
        compile(doc)


def test_a_local_marker_named_like_a_project_one_is_refused(doc):
    with pytest.raises(RostrumError, match="Logo Lands"):
        doc.apply({"op": "marker.add", "args": {"name": "Logo Lands", "at": 1.0}}, Who.person())


HELD = """
pad = track("pad", builtIn="warmPad")
pad.note("D3", at=0.1, dur="next")
pad.note("A3", at="#logo lands", dur={"to": "#logo lands+1.5"})
"""


def test_a_held_note_follows_a_moved_marker(doc):
    """A note tied to "next" or to a marker stays continuous when the marker moves (no gap before it)."""
    doc.run_script("cue.py", run_source(HELD, "cue.py"), Who.script("cue.py"))
    durs = lambda: [n["dur"] for n in compile(doc)["tracks"][0]["notes"]]   # noqa: E731
    assert durs() == [2.4, 1.5]
    project.edit(doc.folder, [{"op": "marker.move", "target": [_id(doc.folder)], "args": {"at": 4.0}}], Who.person())
    assert durs() == [3.9, 1.5]
    project.edit(doc.folder, [{"op": "marker.move", "target": [_id(doc.folder)], "args": {"at": 0.05}}], Who.person())
    with pytest.raises(RostrumError, match="no later note"):
        compile(doc)
