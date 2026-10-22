"""A damaged song never opens half-read, the refusal names it and says nothing was changed, and nothing is written over
it (RELEASE.md line 13). Saving, Duplicate and Open recent are the kit's (shared/gui-kit/tests/test_docfiles.py)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest
from rostrum_core import RostrumError, Who
from rostrum_gui import docfiles
from screensound.files_sound import FILES_SOUND, ITEM, blank


@pytest.mark.parametrize("damage", ["cut short", "wrong shape", "another app", "newer version"])
def test_damaged_song_is_refused_whole(tmp_path, monkeypatch, damage):
    monkeypatch.setenv("ROSTRUM_SETTINGS_DIR", str(tmp_path / "settings"))
    doc = blank(tmp_path / "Lull")
    doc.apply([{"op": "track.add", "args": {"id": "keys", "name": "Keys"}}], Who.person("t"))
    doc.save()
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
        docfiles.open_whole(FILES_SOUND, doc.folder, ITEM)
    words = docfiles.said(e.value)
    assert "\"Lull\"" in words and "Nothing was changed" in words
    assert f.read_bytes() == before
