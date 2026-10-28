"""Guards what would break silently: other people's settings are never lost, changed or overwritten."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import tomlkit  # noqa: E402

from rostrum_connect import ConnectError, add, entries, remove, status  # noqa: E402


@pytest.fixture(autouse=True)
def fake_home(tmp_path, monkeypatch):
    for var in ("HOME", "USERPROFILE"):
        monkeypatch.setenv(var, str(tmp_path / "home"))
    monkeypatch.setenv("APPDATA", str(tmp_path / "home" / "AppData" / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "home" / "AppData" / "Local"))
    monkeypatch.setenv("ROSTRUM_BACKUP_DIR", str(tmp_path / "backups"))
    monkeypatch.setenv("ROSTRUM_CONNECT_NO_CLI", "1")
    monkeypatch.delenv("CODEX_HOME", raising=False)
    monkeypatch.delenv("CLAUDE_CONFIG_DIR", raising=False)
    return tmp_path / "home"


def _put(path: Path, text: str) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return text


def test_add_then_remove_restores_json_and_keeps_other_servers(fake_home):
    f = fake_home / ".cursor" / "mcp.json"
    original = _put(f, json.dumps({"theme": "x", "mcpServers": {"other": {"command": "foo", "args": ["-a"]}}}, indent=4) + "\n")
    assert add("cursor", "2d").ok and add("cursor", "sound").ok and add("cursor", "2d").ok     # re-adding is fine
    assert entries("cursor") == {"other": False, "rostrum-2d": True, "rostrum-sound": True}
    assert json.loads(f.read_text("utf-8"))["mcpServers"]["other"] == {"command": "foo", "args": ["-a"]}
    remove("cursor", "2d"), remove("cursor", "sound")
    assert f.read_text("utf-8") == original


def test_toml_keeps_comments_and_removes_a_table_we_made(fake_home):
    f = fake_home / ".codex" / "config.toml"
    original = _put(f, '# my codex\nmodel = "gpt"\n\n[mcp_servers.other]\ncommand = "foo"  # keep me\n')
    add("codex", "2d")
    assert "# keep me" in f.read_text("utf-8") and "# my codex" in f.read_text("utf-8")
    assert tomlkit.parse(f.read_text("utf-8"))["mcp_servers"]["rostrum-2d"]["env"]["ROSTRUM_ADDED_BY"]
    remove("codex", "2d")
    assert f.read_text("utf-8") == original
    f2 = fake_home / ".gemini" / "antigravity" / "mcp_config.json"                  # a file that had no servers table at all
    _put(f2, '{"a": 1}\n')
    add("antigravity", "sound"), remove("antigravity", "sound")
    assert json.loads(f2.read_text("utf-8")) == {"a": 1}


def test_someone_elses_entry_is_never_overwritten_or_removed(fake_home):
    f = fake_home / ".cursor" / "mcp.json"
    original = _put(f, json.dumps({"mcpServers": {"rostrum-2d": {"command": "mine"}}}))
    assert status("cursor", "2d").foreign
    with pytest.raises(ConnectError):
        add("cursor", "2d")
    with pytest.raises(ConnectError):
        remove("cursor", "2d")
    assert f.read_text("utf-8") == original


def test_file_with_comments_is_refused_and_left_alone(fake_home):
    f = fake_home / "AppData" / "Roaming" / "Zed" / "settings.json"
    original = _put(f, '{\n  // my font\n  "buffer_font_size": 14,\n}\n')
    with pytest.raises(ConnectError, match="comments"):
        add("zed", "2d")
    assert f.read_text("utf-8") == original


def test_antigravity_knows_a_hand_made_entry_and_keeps_other_servers(fake_home):
    f = fake_home / ".gemini" / "antigravity" / "mcp_config.json"
    mine = {"command": "py", "args": ["-m", "rostrum2d.mcp"]}
    other = {"serverUrl": "https://x", "headers": {"Authorization": "secret"}}
    original = _put(f, json.dumps({"mcpServers": {"rostrum-2d": mine, "other": other}}))
    assert status("antigravity", "2d").ours and not status("antigravity", "sound").ours
    assert remove("antigravity", "2d").ok
    assert json.loads(f.read_text("utf-8")) == {"mcpServers": {"other": other}}
    assert json.loads(original)["mcpServers"]["other"] == other
