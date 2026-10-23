"""Two things that keep a scripted run honest: a stale build never beats a fresh one, and a scripted run's default
output folder is never the person's own."""
import os
from pathlib import Path

from rostrum_core import builds, userhome


def test_the_newest_build_wins_whatever_the_folder(tmp_path, capsys):
    old, new = tmp_path / "release" / "x.exe", tmp_path / "agent" / "x.exe"
    for p, t in ((old, 1000), (new, 2000)):
        p.parent.mkdir()
        p.write_bytes(b"x" * t)
        os.utime(p, (t, t))
    assert builds.newest([old, new], "the test engine") == new
    assert str(new) in capsys.readouterr().err                     # says which one it used
    assert builds.newest([tmp_path / "none.exe"], "x") is None


def test_a_scripted_runs_default_output_goes_to_its_scratch_home(tmp_path, monkeypatch):
    monkeypatch.setenv("ROSTRUM_SCRIPTED_HOME", str(tmp_path))
    person = Path("C:/Users/someone/Videos")
    assert userhome.output_dir("exports", person) == tmp_path / "out" / "exports"
