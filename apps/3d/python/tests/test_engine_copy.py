"""The engine runs from a copy: a rebuild (a changed file) gets a new copy, the running one keeps its own."""
import os

from rostrum3d import engine_copy


def test_rebuild_gets_its_own_copy(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("ROSTRUM3D_ENGINE_COPY", raising=False)
    build = tmp_path / "install"
    (build / "qml").mkdir(parents=True)
    (build / "core.exe").write_bytes(b"one")
    (build / "qml" / "view.dll").write_bytes(b"v")
    first = engine_copy.copy_of(build, "3d-core", only=("core.exe",))
    assert (first / "core.exe").read_bytes() == b"one" and not (first / "qml").exists()
    assert engine_copy.copy_of(build, "3d-core", only=("core.exe",)) == first        # same build: same copy
    (build / "core.exe").write_bytes(b"two!")
    os.utime(build / "core.exe", ns=(1, 1))
    second = engine_copy.copy_of(build, "3d-core", only=("core.exe",))
    assert second != first and (second / "core.exe").read_bytes() == b"two!"
    assert (first / "core.exe").read_bytes() == b"one"                             # the running copy is untouched


def test_missing_build_is_returned_as_is(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert engine_copy.copy_of(tmp_path / "nothing", "3d-core") == tmp_path / "nothing"
