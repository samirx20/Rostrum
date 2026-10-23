from rostrum_sound import settings


def test_a_scripted_runs_new_projects_stay_in_its_scratch_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    monkeypatch.setenv("ROSTRUM_SETTINGS_DIR", str(tmp_path / "settings"))
    monkeypatch.delenv("ROSTRUM_PROJECTS_DIR", raising=False)
    assert tmp_path in settings.projects_dir().parents
