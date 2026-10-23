from rostrum2d import settings


def test_a_scripted_export_never_defaults_into_the_persons_videos(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    monkeypatch.delenv("ROSTRUM2D_PROJECTS", raising=False)
    assert tmp_path in settings.videos_dir().parents and tmp_path in settings.projects_dir().parents
