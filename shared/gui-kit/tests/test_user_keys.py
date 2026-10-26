"""Guards the person's own key file (keymap.py): read last, marked "user", a clash or an unknown action is loud."""
import pytest

from rostrum_gui.keymap import KeyMap


def _write(tmp_path, monkeypatch, text):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    (tmp_path / "keys").mkdir(exist_ok=True)
    (tmp_path / "keys" / "mapx.toml").write_text(text, encoding="utf-8")


def test_user_key_wins_and_says_so(tmp_path, monkeypatch):
    _write(tmp_path, monkeypatch, '"undo" = "Ctrl+Alt+U"\n"Add a marker at the playhead" = ""\n')
    km = KeyMap("MapX")
    assert km.job_of("Ctrl+Alt+U") == "undo" and km.job_of("Ctrl+Z") == "" and km.key_of("marker") == ""
    assert {e["job"]: e["origin"] for e in km.entries()}["undo"] == "user"


@pytest.mark.parametrize("text", ['"undo" = "Ctrl+C"', '"nope" = "F5"'])
def test_user_key_clash_or_unknown_is_loud(tmp_path, monkeypatch, text):
    _write(tmp_path, monkeypatch, text)
    with pytest.raises(ValueError, match="mapx.toml"):
        KeyMap("MapX")
