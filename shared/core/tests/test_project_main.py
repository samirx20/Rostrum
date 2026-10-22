"""The project's main mix: every app plays the marked Sound item; a stale mark is loud, never a silent other song."""
import json

import pytest

from rostrum_core import RostrumError, project


def _proj(tmp_path):
    (tmp_path / "docs").mkdir()
    for item, name in (("a_song", "A song"), ("b_voice", "B voice")):
        (tmp_path / "docs" / f"{item}.trk").write_text(json.dumps({"doc": {"name": name}}), encoding="utf-8")
    (tmp_path / "project.json").write_text(json.dumps({"fps": 30, "items": []}), encoding="utf-8")
    return tmp_path


def test_main_mark_round_trip_keeps_other_keys(tmp_path):
    p = _proj(tmp_path)
    assert project.main(p, "sound")["id"] == "a_song"           # no mark: the first by name
    project.set_main(p, "sound", "b_voice")
    assert project.main(p, "sound")["id"] == "b_voice"
    assert json.loads((p / "project.json").read_text(encoding="utf-8"))["fps"] == 30
    project.set_main(p, "sound", None)
    assert "main" not in json.loads((p / "project.json").read_text(encoding="utf-8"))


def test_stale_mark_is_loud(tmp_path):
    p = _proj(tmp_path)
    project.set_main(p, "sound", "b_voice")
    (p / "docs" / "b_voice.trk").unlink()
    with pytest.raises(RostrumError):
        project.main(p, "sound")
    with pytest.raises(RostrumError):
        project.set_main(p, "sound", "nope")
