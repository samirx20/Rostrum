"""A file-format step runs once per song (2026-10-26: the 6 → 7 bass step ran again on every open, because the song
file was folded before it and still said format 6, so each agent session moved the bass another octave down). Open,
edit, close and reopen keeps the notes; undo and redo around the step stay exact; a song already moved twice is put
back on open."""
import copy
import json

import pytest
from rostrum_core import Document, RostrumError, Who, live
from rostrum_core.diff import diff
from rostrum_core.storage import paths
from rostrum_core.who import UPGRADE

from rostrum_sound import KIND, run_source
from rostrum_sound.doc import migrations

A = Who.agent("t")
SONG = """
tempo(120)
b = track("b", builtIn="bass")
for n, p in enumerate(["E2", "A2", "D3", "G2"]):
    b.note(p, at=beat(n), dur=beats(1))
"""
OLD = ["E3", "A3", "D4", "G3"]           # the same song as format 6 held it (played an octave low)
NOW = ["E2", "A2", "D3", "G2"]


def _bass(doc):
    return [n["pitch"] for t in doc.data["tracks"] if t["id"] == "b" for n in t["notes"]]


def _notes(doc):
    return [n["id"] for t in doc.data["tracks"] if t["id"] == "b" for n in t["notes"]]


def _format6_song(folder):
    """A song saved by format 6 with a history, its file written at step 1 (as an agent's server leaves it)."""
    doc = Document.new(KIND, folder, "s")
    doc.run_script("song.py", run_source(SONG.replace('"E2", "A2", "D3", "G2"', ", ".join(f'"{p}"' for p in OLD)),
                                         "song.py"), A)
    doc.save()
    p = paths(folder, "s", KIND.ext)["doc"]
    f = json.loads(p.read_text(encoding="utf-8"))
    p.write_text(json.dumps({**f, "version": 6}, separators=(",", ":")), encoding="utf-8")
    return folder


def _session(folder, tempo):
    """An agent's session: open, one edit through the live door, close without folding the song file."""
    doc = Document.open(folder, "s", KIND)
    live.keep(doc)
    doc.apply([{"op": "doc.set", "target": ["root"], "args": {"tempo": tempo}}], A)
    return doc


def test_open_edit_reopen_three_times_keeps_the_notes(tmp_path):
    folder = _format6_song(tmp_path)
    for n in range(3):
        doc = _session(folder, 121 + n)
        assert _bass(doc) == NOW
    doc.save()
    assert _bass(Document.open(folder, "s", KIND)) == NOW
    ups = [c for c in doc.history.changes if c.format]
    assert [c.format for c in ups] == [[6, migrations.FORMAT]]     # one upgrade step, to the newest format


def test_undo_redo_around_the_step_is_exact_and_the_step_itself_stays(tmp_path):
    folder = _format6_song(tmp_path)
    doc = _session(folder, 121)
    doc.apply([{"op": "note.transpose", "target": _notes(doc), "args": {"semitones": 2}}], A)
    up, moved = [c for c in doc.history.changes if c.format][0], _bass(doc)
    doc.undo(A)
    assert _bass(doc) == NOW
    doc.redo(A)
    assert _bass(doc) == moved
    with pytest.raises(RostrumError, match="brought an older file up to date"):
        doc.undo_changes([up], A)
    doc.history.versions["before"] = 1                  # a version from before the step comes back as it sounded
    doc.restore_version("before", A)
    assert _bass(doc) == NOW
    assert _bass(Document.open(folder, "s", KIND)) == NOW


def test_a_song_moved_twice_by_the_old_bug_is_put_back(tmp_path):
    folder = _format6_song(tmp_path)
    doc = Document.open(folder, "s", KIND)
    live.keep(doc)
    for _ in range(2):          # as builds before the fix wrote it: the step again, without its formats
        work = copy.deepcopy(doc.data)
        for n in work["tracks"][0]["notes"]:
            n["pitch"] = n["pitch"][:-1] + str(int(n["pitch"][-1]) - 1)
        doc.commit(work, diff(doc.data, work, KIND.lists), UPGRADE, "The bass now plays at the written pitch: the "
                   "notes on 1 bass track moved down an octave, so the song sounds as before")
    assert _bass(doc) == ["E0", "A0", "D1", "G0"]
    doc.live.fold()
    doc = Document.open(folder, "s", KIND)
    assert _bass(doc) == NOW and doc.notes and doc.notes[0].startswith("Repaired")
    assert _bass(Document.open(folder, "s", KIND)) == NOW


def _window_session(folder):
    """A window's open and close with no edit: live, windowed, its quiet fold, then the fold on close."""
    doc = Document.open(folder, "s", KIND)
    lv = live.keep(doc)
    lv.windowed()
    lv.fold_if_quiet()
    while lv.fold_work():
        pass
    lv.settle()
    lv.fold(always=False)               # the window's close (live_link.py)
    return doc


def _agrees(folder):
    """The song file's step is in its history, and the history replayed from its start gives the same song."""
    p = paths(folder, "s", KIND.ext)
    f = json.loads(p["doc"].read_text(encoding="utf-8"))
    on_disk = sum('"seq"' in line for line in p["history"].read_text(encoding="utf-8").splitlines())
    assert f["at"] <= on_disk                       # on disk, before any open could put it right
    doc = Document.open(folder, "s", KIND)
    assert doc.at_step(doc.seq) == doc.data
    return doc


def test_open_and_close_in_a_window_with_no_edit_keeps_the_sound(tmp_path):
    folder = _format6_song(tmp_path)
    for _ in range(3):                  # critic r9: the file counted the upgrade, the history never got it: +12 on reopen
        _window_session(folder)
        assert _bass(_agrees(folder)) == NOW


def test_a_file_that_counts_a_step_its_history_lacks_is_kept_and_the_step_recorded(tmp_path):
    from rostrum_core.storage import canonical, doc_hash, write_document
    folder = _format6_song(tmp_path)
    doc = Document.open(folder, "s", KIND)          # as builds before the fix left it: the file written, the history not
    body = canonical(doc.data)
    write_document(paths(folder, "s", KIND.ext)["doc"], KIND.format, KIND.version, doc.seq, doc.history.changes[-1].t,
                   body, doc_hash(doc.data))
    doc = Document.open(folder, "s", KIND)
    assert _bass(doc) == NOW and "lacked" in doc.notes[-1]
    _window_session(folder)
    for _ in range(2):
        assert _bass(_agrees(folder)) == NOW
