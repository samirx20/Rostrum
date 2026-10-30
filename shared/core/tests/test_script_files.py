"""run_script's scripts as files in <project>/scripts (rostrum_core/mcp/script_files.py)."""
from types import SimpleNamespace

from rostrum_core.mcp import script_files as SF


def ctx(folder):
    return SimpleNamespace(app=SimpleNamespace(folder=str(folder) if folder else None))


def test_inline_source_is_saved_once_said(tmp_path):
    c = ctx(tmp_path)
    said = SF.save(c, {"source": "x = 1"}, "song.py")
    p = tmp_path / "scripts" / "song.py"
    assert p.read_text(encoding="utf-8") == "x = 1" and str(p) in said and '{"name": "song.py"}' in said
    assert SF.save(c, {"source": "x = 2"}, "song.py") is None          # known file: kept up to date, not said again
    assert p.read_text(encoding="utf-8") == "x = 2"
    assert SF.save(c, {"source": "x"}, "intro") and (tmp_path / "scripts" / "intro.py").is_file()


def test_nothing_saved_without_a_project_or_for_a_path_name(tmp_path):
    assert SF.save(ctx(None), {"source": "x"}, "a.py") is None
    assert SF.save(ctx(tmp_path), {"source": "x"}, "../a.py") is None
    assert SF.save(ctx(tmp_path), {"path": "C:/a.py"}, "a.py") is None


def test_name_only_and_relative_paths_find_the_file(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "song.py").write_text("x", encoding="utf-8")
    (tmp_path / "top.py").write_text("x", encoding="utf-8")
    c = ctx(tmp_path)
    assert SF.resolve(c, {"name": "song.py"})["path"] == str(tmp_path / "scripts" / "song.py")
    assert SF.resolve(c, {"name": "song"})["path"] == str(tmp_path / "scripts" / "song.py")
    assert SF.resolve(c, {"path": "top.py"})["path"] == str(tmp_path / "top.py")
    assert SF.resolve(c, {"path": "song.py"})["path"] == str(tmp_path / "scripts" / "song.py")
    assert "path" not in SF.resolve(c, {"name": "other.py"})                 # no file: the usual "needs source or path"
    assert SF.resolve(c, {"source": "x", "name": "song.py"}) == {"source": "x", "name": "song.py"}
