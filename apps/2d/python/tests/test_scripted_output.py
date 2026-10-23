from pathlib import Path

from rostrum2d import settings


def test_a_scripted_export_never_defaults_into_the_persons_videos(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    monkeypatch.delenv("ROSTRUM2D_PROJECTS", raising=False)
    assert tmp_path in settings.videos_dir().parents and tmp_path in settings.projects_dir().parents


def test_the_folder_the_sheet_shows_is_the_folder_the_file_is_written_to(tmp_path, monkeypatch):
    """Guards the sheet's "Folder" line: with no project, a scripted run's file goes to its scratch home, and says so."""
    from rostrum2d.mcp import exporting
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))

    def fake_to_file(where, scene, fmt, s, target, *a):
        target.write_bytes(b"x")
        return {}
    monkeypatch.setattr(exporting, "_to_file", fake_to_file)
    scene = {"comp": {"id": "c", "props": {"width": 32, "height": 16, "fps": 10, "duration": 1.0}}}
    shown = exporting.default_folder(None, None)
    facts = exporting.run("t", scene, "mp4", exporting.settings("t", "mp4", 1.0))
    assert tmp_path in shown.parents
    assert Path(facts["file"]).parent == shown
