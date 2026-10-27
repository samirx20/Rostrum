"""fit_loudness: a render that landed under the target gets an exact edit that reaches it. Guards: the balance-keeping
option touches only the master's maxLimit; the trim option lands the next render on the target within maxLimit; the
tame-peaks option, applied as its ops, lands on the target within maxLimit with every track where it was against the mix."""
from rostrum_core import Document, Who

from rostrum_sound import KIND
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
        keep, trim = (next(o for o in p["options"] if o["name"] == n) for n in ("keep_balance", "trim_track"))
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


def test_taming_the_peaks_reaches_the_target_within_the_limit_with_the_balance_kept(tmp_path):
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"))
    doc.apply([{"op": "master.set", "target": ["master"], "args": {"maxLimit": 2}}], Who.person())
    master = doc.data["master"][0]
    rel = lambda r: {t["id"]: t["lufs"] - r["lufs"] for t in r["tracks"]}         # each track against the mix
    with Engine() as e:
        first = e.request("render", schedule=compile(doc.data), out=str(tmp_path / "a.wav"), stems=[])
        assert master["loudness"] - first["lufs"] > 1, first["lufs"]               # this song lands ~2.5 dB under with 2 dB allowed
        p = fit.plan(first, master, {t["id"]: t for t in doc.data["tracks"]}, doc.data, e, tmp_path)
        tame = next(o for o in p["options"] if o["name"] == "tame_peaks")
        assert tame.get("ops") and p["best"] == "tame_peaks", p["words"]
        doc.apply(tame["ops"], Who.agent("fit"))
        after = e.request("render", schedule=compile(doc.data), out=str(tmp_path / "b.wav"), stems=[])
    assert abs(after["lufs"] - master["loudness"]) <= 0.5, after["lufs"]
    assert after["master"]["limiterMaxReductionDb"] <= 2.1, after["master"]
    for w in tame["tracks"]:
        assert abs(rel(after)[w] - rel(first)[w]) <= 0.5, (w, rel(first), rel(after))


def test_a_track_whose_own_peak_stands_over_0_dbfs_still_gets_every_option(tmp_path):
    """Critic r12: a quiet fader on a loud part puts the track's own peak (before its fader) over 0 dBFS; the first trial
    threshold (that peak minus the depth) was outside the compressor's -80…0 and sank the whole plan, keep_balance too."""
    from rostrum_sound import fit_peaks as peaks
    doc = Document.new(KIND)
    doc.run_script("song.py", run_source(SONG, "song.py"))
    doc.apply([{"op": "master.set", "target": ["master"], "args": {"maxLimit": 2}},
               {"op": "track.set", "target": ["piano"], "args": {"volume": 0.05}}], Who.person())   # -26 dB: its own peak far over 0
    master = doc.data["master"][0]
    with Engine() as e:
        first = e.request("render", schedule=compile(doc.data), out=str(tmp_path / "a.wav"), stems=[])
        t = peaks.Tamer(doc.data, e, tmp_path, first)
        assert t.peak["piano"] > 0, t.peak                                       # the case: its own peak over 0 dBFS
        assert all(peaks.LOWEST <= t.threshold("piano", d) <= peaks.HIGHEST for d in (0, 1, 4, 18, 200))
        p = fit.plan(first, master, {tr["id"]: tr for tr in doc.data["tracks"]}, doc.data, e, tmp_path, "piano")
        quick = fit.plan(first, master, {tr["id"]: tr for tr in doc.data["tracks"]}, doc.data, e, tmp_path, only="keep_balance")
    keep = next(o for o in p["options"] if o["name"] == "keep_balance")
    assert keep.get("ops"), p["words"]
    assert [o["name"] for o in quick["options"]] == ["keep_balance"] and quick["options"][0]["ops"] == keep["ops"]
    for o in p["options"]:                                                  # every compressor setting proposed is one it takes
        for op in o.get("ops") or []:
            if op["op"] in ("effect.add", "effect.set") and "threshold" in op["args"]:
                assert peaks.LOWEST <= op["args"]["threshold"] <= peaks.HIGHEST, op


def test_one_option_that_fails_leaves_the_others():
    def boom():
        raise RuntimeError("engine said no")
    got = fit._alone("tame_peaks", boom)
    assert got["impossible"] and "engine said no" in got["words"] and not got.get("ops")
