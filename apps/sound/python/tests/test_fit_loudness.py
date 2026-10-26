"""fit_loudness: a render that landed under the target gets an exact edit that reaches it. Guards: the balance-keeping
option touches only the master's maxLimit; the trim option lands the next render on the target within maxLimit."""
from rostrum_sound import fit_loudness as fit
from rostrum_sound import run_source
from rostrum_sound.compile import compile
from rostrum_sound.engine import Engine

from test_gentle_limiting import SONG


def test_solve_finds_the_smallest_trim_and_refuses_what_cannot_be_reached():
    short = lambda d: max(0.0, 3.0 - 0.8 * d)           # a mix whose shortfall falls 0.8 dB per dB trimmed
    got = fit.solve(short, 3.0)
    assert short(got) < fit.SHORT_OK <= short(got - 0.2), got
    assert fit.solve(lambda d: 1.0, 1.0) is None


def test_the_exact_edit_reaches_the_target_within_the_masters_limit(tmp_path):
    root = run_source(SONG, "fit.py")
    data = getattr(root, "data", root)
    master = (data.get("master") or [{}])[0]
    master["maxLimit"] = 4                                       # this song needs ~4.7 dB; the master allows 4: a trim can close the rest
    tracks = {t["id"]: t for t in data["tracks"]}
    with Engine() as e:
        first = e.request("render", schedule=compile(data), out=str(tmp_path / "a.wav"), stems=[])
        assert first["master"]["heldDb"] > 0.1, first["master"]            # the first render lands under the target
        p = fit.plan(first, master, tracks, data, e, tmp_path)
        keep, trim = p["options"]
        assert keep["ops"] == [{"op": "master.set", "target": ["master"], "args": {"maxLimit": keep["max_limit_db"]}}]     # no volume moves: the balance is as written
        assert keep["max_limit_db"] >= fit.need_db(first)
        assert trim["trim_db"] > 0 and trim["volume"] < trim["was"], trim
        after = e.request("render", schedule=compile(fit.trimmed(data, trim["track"], trim["trim_db"])), out=str(tmp_path / "b.wav"), stems=[])
    goal = master["loudness"]
    master["maxLimit"] = keep["max_limit_db"]                    # the balance-keeping edit, applied: the target is met as written
    with Engine() as e:
        kept = e.request("render", schedule=compile(data), out=str(tmp_path / "c.wav"), stems=[])
    assert abs(kept["lufs"] - goal) <= 0.5, kept["lufs"]
    assert abs(after["lufs"] - goal) <= 0.5 and after["master"]["limiterMaxReductionDb"] <= 4.1, after["master"]
