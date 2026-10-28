"""The Render button never says a confident wrong time on a computer's first render (a 56 s render said "about 9 s"):
with no kept measurement and no speed learned from an earlier render there is no number, only "measuring the time"."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum3d import estimate_job  # noqa: E402
from rostrum_core.cache import CACHE  # noqa: E402
from screen3d import render_guess  # noqa: E402

S = {"renderer": "cycles", "samples": 128, "width": 1920, "height": 1080}


def test_first_render_has_no_number_until_a_render_has_been_timed(tmp_path, monkeypatch):
    monkeypatch.setattr(CACHE, "root", tmp_path)
    monkeypatch.setattr(estimate_job, "cached", lambda *a, **k: None)
    assert render_guess.guess({}, S, exe="x") == (0.0, False)
    assert render_guess.words(0.0, False) == "measuring the time"
    render_guess.learn(S, 56.0)                          # a first render landed
    seconds, measured = render_guess.guess({}, S, exe="x")
    assert not measured and 40 < seconds < 70            # this computer's own speed, said as a first guess
