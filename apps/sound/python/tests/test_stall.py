"""A build that goes flat before its peak is a fault naming the flat part; a part held at one level for many bars in a
piece asked to build is a warning (listen/stall.py, stall_parts.py, static_part.py)."""
from types import SimpleNamespace

from rostrum_sound.listen import stall, stall_parts, static_part

BAR = 4 * 60 / 66      # one 4/4 bar at 66 BPM


def _rows(lufs, per_beat=(2, 2, 2), bright=(-13, -13, -13)):
    return [{"bar": 9 + i, "from_s": round((8 + i) * BAR, 2), "to_s": round((9 + i) * BAR, 2), "lufs": l, "per_beat": p,
             "bright_db": b} for i, (l, p, b) in enumerate(zip(lufs, per_beat, bright))]


def _track(tid, vel_of, bars=range(30), **more):
    """One whole-bar note per bar, velocity vel_of(bar)."""
    return {"id": tid, "type": "track", "instrument": "builtIn", "builtIn": tid,
            "notes": [{"id": f"{tid}{b}", "pitch": 60, "at": {"beat": 4 * b}, "dur": {"beats": 4}, "vel": vel_of(b)} for b in bars],
            **more}


def test_rising_build_passes_and_flat_last_bars_fail():
    assert stall.decide(_rows((-18.7, -16.7, -15.3))) is None                       # the rival: +3.4 LU
    got = stall.decide(_rows((-16.4, -15.0, -16.3), bright=(-14.3, -13.3, -12.0)))  # new r1: flat, a cymbal swell on top
    assert got == {"rise_lu": 0.1, "denser_x": 1.0, "brighter_db": 2.3}
    assert stall.decide(_rows((-16.4, -16.0, -16.3), per_beat=(2, 2, 3))) is None   # busier: still a build


def test_the_flat_part_is_named_and_the_rising_one_is_not():
    data = {"tempo": 66, "tracks": [_track("strings", lambda b: 0.6), _track("horns", lambda b: 0.3 + 0.05 * b)]}
    flat = stall_parts.flat(data, _rows((-16.4, -15.0, -16.3)))
    assert [p["track"] for p in flat] == ["strings"]
    what, fix, when = stall.words(_rows((-16.4, -15.0, -16.3)), {"rise_lu": 0.1, "denser_x": 1.0, "brighter_db": 0.0},
                                  flat, 38.0, "climax")
    assert "bars 9–11" in when and "strings" in what and 'build_to("#climax"' in fix and 'parts=["strings"]' in fix


def test_static_part_is_a_warning_only_when_the_brief_builds():
    steady = _track("strings", lambda b: 0.6 + 0.02 * (b % 2))                       # ±1.6 %: one level
    swelling = _track("horns", lambda b: round(0.1 * 1.07 ** b, 3))             # +7 % a bar: a real swell
    doc = SimpleNamespace(folder=None, data={"tempo": 66, "brief": "Begins quiet and builds steadily to a climax at 38 s.",
                                             "tracks": [steady, swelling]})
    said = static_part.warnings(doc)
    assert len(said) == 1 and said[0].startswith("static part: strings") and "bars 1–30" in said[0]
    doc.data["brief"] = "A calm piano loop."
    assert static_part.warnings(doc) == []
