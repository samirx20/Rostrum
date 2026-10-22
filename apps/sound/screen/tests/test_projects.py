"""A person's songs are never lost: an untitled song is on disk from its first change, Save As keeps every change and
refuses to overwrite, and a song left open by a crash is found again."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from rostrum_core import RostrumError, Who
from screensound import projects


@pytest.fixture(autouse=True)
def here(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SETTINGS_DIR", str(tmp_path / "settings"))
    return tmp_path


def _add_track(doc):
    doc.apply([{"op": "track.add", "args": {"id": "keys", "name": "Keys"}}], Who.person("t"))
    doc.save()


def test_save_as_keeps_changes_and_removes_untitled(here):
    doc = projects.new_song()
    assert projects.is_untitled(doc.folder)
    _add_track(doc)
    dest = projects.save_as(doc.folder, doc.item_id, here / "My song")
    assert not doc.folder.exists()
    again = projects.open_song(dest, projects.ITEM)
    assert again.has("keys") and len(again.history.changes) == 1
    assert projects.save_as(dest, projects.ITEM, dest) == dest.resolve()      # same folder: nothing to do
    (here / "full").mkdir()
    (here / "full" / "x.txt").write_text("x")
    with pytest.raises(RostrumError):
        projects.save_as(dest, projects.ITEM, here / "full")                   # has files: refused


def test_crashed_untitled_song_is_offered_back(here):
    doc = projects.new_song()
    _add_track(doc)
    projects.lock(doc.folder)
    assert projects.to_recover() == []                 # this process is alive: not a crash
    (doc.folder / projects.LOCK).write_text(json.dumps({"pid": 999999, "at": 0}), encoding="utf-8")
    assert projects.to_recover() == [doc.folder]


def test_recent_drops_missing_songs(here):
    doc = projects.new_song()
    dest = projects.save_as(doc.folder, doc.item_id, here / "Kept")
    projects.remember(dest, projects.ITEM)
    projects.remember(here / "gone", "song")
    assert [r["name"] for r in projects.recent()] == ["Kept"]
