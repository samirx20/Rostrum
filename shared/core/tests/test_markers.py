"""The project's shared markers: every app reads them, so saving, history and loud errors must hold."""
import pytest

from rostrum_core import RostrumError, Who
from rostrum_core import markers as M
from rostrum_core.mcp.context import App
from rostrum_core.mcp.server import Runtime


def test_markers_saved_with_history_and_authors(tmp_path):
    sam, agent = Who.person("sam"), Who.agent("claude")
    assert M.listing(tmp_path) == []
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "logo lands", "at": 2.5}}], sam)
    mid = M.listing(tmp_path)[0]["id"]
    M.edit(tmp_path, [{"op": "marker.move", "target": [mid], "args": {"at": 3.0}},
                      {"op": "marker.rename", "target": [mid], "args": {"name": "Logo lands"}}], agent)
    (m,) = M.listing(tmp_path)
    assert (m["id"], m["name"], m["at"], m["by"], m["changed_by"]) == (mid, "Logo lands", 3.0, "person:sam", "agent:claude")
    assert M.at(tmp_path, "logo LANDS+0.5") == 3.5
    doc = M.open_markers(tmp_path)
    doc.undo(agent)
    assert doc.data["markers"][0]["at"] == 2.5


def test_markers_fail_loudly(tmp_path):
    who = Who.person()
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "drop", "at": 1}}], who)
    with pytest.raises(RostrumError, match="drop"):
        M.edit(tmp_path, [{"op": "marker.add", "args": {"name": " Drop ", "at": 4}}], who)
    with pytest.raises(RostrumError, match="drop"):
        M.at(tmp_path, "drpo")
    with pytest.raises(RostrumError, match="both a project marker"):      # decided S11: a clash is an error
        M.refuse_clashes(M.times(tmp_path), ["intro", "DROP"], "sound doc")
    assert M.used(M.times(tmp_path), ["drop"]) == {"drop": 1.0}


def test_marker_tools(tmp_path):
    rt = Runtime(App("rostrum-test", {}, folder=str(tmp_path)))
    reply, _ = rt.call("edit_markers", {"ops": [{"op": "marker.add", "args": {"name": "hit", "at": 1.25}}]}, Who.agent("a"))
    assert reply["data"]["markers"][0]["by"] == "agent:a"
    reply, _ = rt.call("inspect_markers", {"name": "hit-0.25"}, Who.agent("a"))
    assert reply["data"]["at"] == 1.0


def test_markers_copied_without_history_are_read(tmp_path):
    """S42: a project copied without its .rostrum folder (the Lull sample a person opens) still has its markers;
    reading only the history file left 2D placing a key on a marker it said wasn't there."""
    M.edit(tmp_path, [{"op": "marker.add", "args": {"name": "noise", "at": 0.5}}], Who.person())
    M.open_markers(tmp_path).save()
    copy = tmp_path / "copy"
    (copy / "docs").mkdir(parents=True)
    (copy / "docs" / "markers.mkr").write_bytes((tmp_path / "docs" / "markers.mkr").read_bytes())
    assert M.times(copy) == {"noise": 0.5}
    assert M.version(copy) > 0
