"""Export's push is measured on the song as it will be written (fit_loudness.reach), never predicted from another render:
a peaky mix under a low Most limiting, pushed, must land on its target (FRICTION #14: the old prediction was 1.5 dB short)."""
from types import SimpleNamespace

from rostrum_sound import fit_loudness as fit
from rostrum_sound import run_source
from rostrum_sound.compile import compile
from rostrum_sound.engine import Engine

from test_gentle_limiting import SONG


def test_the_measured_push_lands_the_file_on_the_target(tmp_path):
    root = run_source(SONG, "fit.py")
    data = getattr(root, "data", root)
    master = data["master"][0]
    master["maxLimit"] = 1.0
    with Engine() as e:
        got = fit.reach(SimpleNamespace(data=data, folder=None), e, tmp_path)
        assert got["reaches"] and got["max_limit_db"] > 1.0 and master["maxLimit"] == 1.0, got     # the song itself untouched
        master.update(got["ops"][0]["args"])
        r = e.request("render", schedule=compile(data), out=str(tmp_path / "f.wav"), stems=[])
    assert abs(r["lufs"] - master["loudness"]) <= fit.REACH_OK, (r["lufs"], got)
    master["maxLimit"] = got["max_limit_db"] + 2
    with Engine() as e:
        assert fit.reach(SimpleNamespace(data=data, folder=None), e, tmp_path) == {}                 # already reaches: nothing
