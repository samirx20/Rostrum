"""The Render button never says a confident wrong time (a 56 s render said "about 9 s" from the reference laptop's
figures, a 96 s one "about 7 s" from this computer's last Render of another scene): with nothing measured for this scene
there is no number, only "measuring the time", until the frame's own steps give a rate."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum3d import estimate_job  # noqa: E402
from screen3d import render_guess  # noqa: E402

S = {"renderer": "cycles", "samples": 128, "width": 1920, "height": 1080}


def test_no_number_until_this_scene_is_measured(monkeypatch):
    monkeypatch.setattr(estimate_job, "cached", lambda *a, **k: None)
    assert render_guess.guess({}, S, exe="x") == (0.0, False)
    assert render_guess.words(0.0) == "measuring the time"
    assert render_guess.left((0.10, 5000.0), (0.30, 9000.0)) == 14.0 + render_guess.WRITE_S   # the frame's own rate
