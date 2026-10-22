"""A person's songs are never lost: a new song is on disk at once (in the projects folder), Duplicate keeps every
change, leaves the original and refuses to overwrite, and an untitled song left open by a crash is found again."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from rostrum_core import RostrumError, Who
from screensound import projects


@pytest.fixture(autouse=True)
def here(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SETTINGS_DIR", str(tmp_path / "settings"))
    monkeypatch.setenv("ROSTRUM_PROJECTS_DIR", str(tmp_path / "projects"))
    return tmp_path


def _add_track(doc):
    doc.apply([{"op": "track.add", "args": {"id": "keys", "name": "Keys"}}], Who.person("t"))
    doc.save()


def test_new_song_is_named_and_duplicate_keeps_the_original(here):
    doc = projects.new_song()
    assert doc.folder.name == "Untitled song" and not projects.is_untitled(doc.folder)
    assert projects.new_song().folder.name == "Untitled song 2"
    _add_track(doc)
    dest = projects.duplicate(doc.folder, doc.item_id, here / "My song")
    assert doc.folder.exists()
    again = projects.open_song(dest, projects.ITEM)
    assert again.has("keys") and len(again.history.changes) == 1
    assert projects.duplicate(dest, projects.ITEM, dest) == dest.resolve()      # same folder: nothing to do
    (here / "full").mkdir()
    (here / "full" / "x.txt").write_text("x")
    with pytest.raises(RostrumError):
        projects.duplicate(dest, projects.ITEM, here / "full")                   # has files: refused


def test_crashed_untitled_song_is_offered_back(here):
    folder = projects.untitled_root() / "untitled-1"             # a song from before saving was automatic
    doc = projects.Document(projects.KIND, projects.Document.new(projects.KIND).data, folder=folder, item=projects.ITEM)
    doc.save()
    _add_track(doc)
    projects.lock(doc.folder)
    assert projects.to_recover() == []                 # this process is alive: not a crash
    (doc.folder / projects.LOCK).write_text(json.dumps({"pid": 999999, "at": 0}), encoding="utf-8")
    assert projects.to_recover() == [doc.folder]


def test_recent_drops_missing_songs(here):
    doc = projects.new_song()
    dest = projects.duplicate(doc.folder, doc.item_id, here / "Kept")
    shutil.rmtree(doc.folder)
    projects.remember(dest, projects.ITEM)
    projects.remember(here / "gone", "song")
    assert [r["name"] for r in projects.recent()] == ["Kept"]


@pytest.mark.parametrize("damage", ["cut short", "wrong shape", "another app", "newer version"])
def test_damaged_song_is_refused_whole(here, damage):
    """RELEASE.md line 13: a damaged song never opens half-read, and nothing is written over it."""
    doc = projects.new_song()
    _add_track(doc)
    f = doc.folder / "docs" / "song.trk"
    text = f.read_text(encoding="utf-8")
    head = json.loads(text)
    if damage == "cut short":
        f.write_text(text[:200], encoding="utf-8")
    else:
        head.update({"wrong shape": {"doc": {"tracks": [{"name": "no id"}]}}, "another app": {"format": "rostrum-2d"},
                     "newer version": {"version": 99}}[damage])
        f.write_text(json.dumps(head), encoding="utf-8")
        (doc.folder / ".rostrum" / "song.history.jsonl").unlink()
    before = f.read_bytes()
    with pytest.raises(RostrumError) as e:
        projects.open_song(doc.folder, projects.ITEM)
    assert '"' + doc.folder.name + '"' in str(e.value)
    assert f.read_bytes() == before
