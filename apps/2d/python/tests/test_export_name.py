"""An export never replaces a file by accident, and its name is the project's in plain words (any language)."""
import pytest
from rostrum_core.errors import RostrumError

from rostrum2d.engine import EngineError
from rostrum2d.mcp import export_name, exporting
from test_export_run import SCENE, DyingEngine


def test_existing_file_is_kept_unless_overwrite(tmp_path):
    f = tmp_path / "a.webm"
    f.write_bytes(b"mine")
    s = exporting.settings("t", "webm", 1.0)
    with pytest.raises(RostrumError, match="already exists"):
        exporting.run("t", SCENE, "webm", s, out=f, engine_factory=DyingEngine)
    assert f.read_bytes() == b"mine"
    with pytest.raises(RostrumError, match="encoder died"):                 # with overwrite it gets as far as the engine
        exporting.run("t", SCENE, "webm", s, out=f, engine_factory=DyingEngine, overwrite=True)


def test_names_and_keep_both(tmp_path):
    one = [{"id": "main", "name": "Main"}]
    assert export_name.file_stem("Zoë Müller", one, "main", "main") == "Zoë Müller"
    two = one + [{"id": "credits", "name": "Credits"}]
    assert export_name.file_stem("Title walk", two, "main", "main") == "Title walk - Main"
    assert export_name.file_stem('a/b:c?', one, "main") == "a b c"
    (tmp_path / "x.mp4").touch()
    assert export_name.free_path(tmp_path / "x.mp4").name == "x 2.mp4"
