"""The dev engine build is started from a run copy in the cache, never straight from engine/target."""
from rostrum2d import settings


def test_dev_engine_runs_from_the_cache_not_target(tmp_path, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    monkeypatch.delenv("ROSTRUM_ENGINE_COPY", raising=False)
    monkeypatch.delenv("ROSTRUM2D_ENGINE", raising=False)
    app = tmp_path / "apps" / "2d"
    exe = app / "engine" / "target" / "agent" / f"rostrum2d-render{settings.EXE}"
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"x")
    monkeypatch.setattr(settings, "APP", app)
    got = settings.engine_exe()
    assert got.is_file() and (app / "engine" / "target") not in got.parents and "2d-" in str(got)
    monkeypatch.setenv("ROSTRUM2D_ENGINE", str(exe))              # the launcher names the build: copied too
    assert settings.engine_exe() == got
