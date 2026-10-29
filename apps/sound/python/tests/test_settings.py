"""The person's settings survive a save and reload, a bad value is refused loudly (never saved), and the engine is
found in the documented order: ROSTRUM_SOUND_ENGINE, the setting, the installed copy, the developer build."""
import pytest
from rostrum_core import RostrumError

from rostrum_sound import settings


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SETTINGS_DIR", str(tmp_path / "settings"))
    for var in ("ROSTRUM_SOUND_ENGINE", "ROSTRUM_HOME", "ROSTRUM_AUDIO_OUTPUT", "ROSTRUM_AUDIO_PERIOD_MS"):
        monkeypatch.delenv(var, raising=False)
    return tmp_path


def test_round_trip_and_refusal(home):
    settings.set("loudness", -16)
    settings.set("exclusive", True)
    settings.set("buffer", 5)
    assert settings.load()["loudness"] == -16
    for name, bad in (("loudness", 3), ("buffer", 7), ("nope", 1)):
        with pytest.raises(RostrumError):
            settings.set(name, bad)
    assert settings.load()["loudness"] == -16
    assert settings.audio_env() == {"ROSTRUM_AUDIO_PERIOD_MS": "5"}


def test_engine_order(home, monkeypatch):
    chosen, installed = home / "chosen.exe", home / "app" / "engines" / settings.EXE
    installed.parent.mkdir(parents=True)
    installed.write_text("")
    monkeypatch.setenv("ROSTRUM_HOME", str(home / "app"))
    assert settings.engine_path() == installed
    chosen.write_text("")
    settings.set("engine", str(chosen))
    assert settings.engine_path() == chosen
    monkeypatch.setenv("ROSTRUM_SOUND_ENGINE", str(home / "missing.exe"))
    with pytest.raises(RostrumError, match="missing.exe"):
        settings.engine_path()


def test_dev_engine_runs_from_the_cache_not_target(home, monkeypatch):
    monkeypatch.setenv("LOCALAPPDATA", str(home / "local"))
    monkeypatch.delenv("ROSTRUM_ENGINE_COPY", raising=False)
    monkeypatch.setattr(settings, "DEV_BUILD", home / "target")
    exe = home / "target" / "agent" / settings.EXE
    exe.parent.mkdir(parents=True)
    exe.write_bytes(b"x")
    got = settings.engine_path()
    assert got.is_file() and (home / "target") not in got.parents and "engine-cache" in str(got) and "sound-" in str(got)
