"""One ending fault, bad_ending (listen/end_check.py): dead air, a cut, a delivery fade, an unresolved last chord and parts
dropping out early, each named with its number; a ring that dies into the file's end passes it and the quiet-ending arc."""
from types import SimpleNamespace

import numpy as np
import soundfile as sf
from rostrum_core import Document

from rostrum_sound import KIND, run_source
from rostrum_sound.listen import arc, end_check

SR = 48000


def _wav(path, tail, seconds=14.0, body_s=8.0):
    """A loud tone for `body_s`, then `tail(t from the tail's start)` as a gain (1 = as loud as the body)."""
    t = np.arange(int(seconds * SR)) / SR
    env = np.where(t < body_s, 1.0, tail(np.maximum(t - body_s, 0)))
    y = 0.3 * np.sin(2 * np.pi * 220 * t) * env
    sf.write(path, np.stack([y, y], axis=1), SR, subtype="PCM_24")
    return str(path)


def _doc(brief=None, script=None):
    if script is None:
        return SimpleNamespace(data={"brief": brief} if brief else {}, folder=None)
    doc = Document.new(KIND)
    doc.run_script("s.py", run_source(script, "s.py"))
    return doc


def _ids(got):
    return [f["id"] for f in got]


def test_a_silent_tail_is_dead_air_and_a_ring_into_the_end_passes(tmp_path):
    silent = _wav(tmp_path / "silent.wav", lambda s: np.where(s < 4.8, 10 ** (-15 / 20), 0.0))   # gone 1.2 s early
    got = end_check.fault(_doc(), None, silent)
    assert _ids(got) == ["bad_ending"] and "dead air" in got[0]["what"] and 'ending("ring"' in got[0]["fix"]
    ring = _wav(tmp_path / "ring.wav", lambda s: 10 ** ((-20 - 3 * s) / 20), seconds=13.0)   # -20 dB dying to -35 at the end
    assert end_check.fault(_doc(), None, ring) == []
    assert end_check.fault(_doc(), None, silent, end_s=12.4) == []          # the silence is past the asked end: a ring may run on


def test_a_piece_that_sits_near_silent_long_before_its_end_dies_early(tmp_path):
    early = _wav(tmp_path / "early.wav", lambda s: np.full_like(s, 10 ** (-36 / 20)))   # 6 s at -36 dB under the body
    got = end_check.fault(_doc(), None, early)
    assert _ids(got) == ["bad_ending"] and "dies early" in got[0]["what"] and "velocity" not in got[0]["fix"]


def test_a_loop_must_not_drop_at_its_end(tmp_path):
    loop = _doc("A 30 s bed that loops seamlessly under a voice")
    full = _wav(tmp_path / "full.wav", lambda s: np.ones_like(s))
    assert end_check.fault(loop, None, full) == []                           # still playing: what a loop wants
    dropped = _wav(tmp_path / "dropped.wav", lambda s: np.where(s < 5.3, 1.0, 0.0))
    got = end_check.fault(loop, None, dropped)
    assert _ids(got) == ["bad_ending"] and "loop drops" in got[0]["what"] and "into bar 1" in got[0]["fix"]


def test_a_file_that_stops_while_playing_is_cut(tmp_path):
    held = _wav(tmp_path / "held.wav", lambda s: np.ones_like(s))
    got = end_check.fault(_doc(), None, held)
    assert _ids(got) == ["bad_ending"] and "chopped:" in got[0]["what"]
    assert end_check.fault(_doc("it ends on a hard stop"), None, held) == []


def test_a_delivery_fade_is_a_fault_unless_the_song_asks_for_a_fade(tmp_path):
    t_fade = 13.0
    faded = _wav(tmp_path / "faded.wav", lambda s: 10 ** (-8 / 20) * np.clip(14.0 - 8.0 - s, 0, 1))   # faded over the last 1 s
    rec = {"faded_s": 1.0, "rang_s": 2.0, "from_s": t_fade}
    got = end_check.fault(_doc(), rec, faded)
    assert _ids(got) == ["bad_ending"] and "faded:" in got[0]["what"]
    asked = SimpleNamespace(data={"ending": {"kind": "fade", "at": "#end"}}, folder=None)
    assert end_check.fault(asked, rec, faded) == []
    assert end_check.fault(_doc("A bed that should fade out at the end"), rec, faded) == []
    assert _ids(end_check.fault(_doc(), rec)) == ["bad_ending"]               # no file to read: deliver's word stands


def test_a_last_chord_off_home_is_unresolved_when_an_ending_is_asked():
    body = 'key("C major")\ntempo(120)\ntrack("p", builtIn="piano").chord(["C3", "E3", "G3"], 0, 4).chord(["F3", "A3", "C4"], 4, 4)'
    got = end_check.fault(_doc(script='brief("ends cleanly on a final chord")\n' + body), None)
    assert _ids(got) == ["bad_ending"] and "unresolved" in got[0]["what"] and "stands on F" in got[0]["what"]
    assert end_check.fault(_doc(script=body), None) == []                    # no ending asked: a loop may stop anywhere
    home = body.replace('["F3", "A3", "C4"]', '["C3", "E3", "G3", "C4"]')
    assert end_check.fault(_doc(script='brief("ends cleanly on a final chord")\n' + home), None) == []


def test_parts_dropping_out_before_the_landing_thin_the_ending():
    s = ('brief("ends cleanly")\nkey("C major")\ntempo(120)\n'
         'track("a", builtIn="piano").note("C3", 0, 20).note("C3", 20, 4)\n'
         'track("b", builtIn="strings").note("E4", 0, 10)\n'
         'track("c", builtIn="flute").note("G4", 0, 10)\n')
    got = end_check.fault(_doc(script=s), None)
    assert _ids(got) == ["bad_ending"] and "drop out early" in got[0]["what"] and "2 of the 3" in got[0]["what"]


def test_a_quiet_ring_passes_the_quiet_ending_arc_and_the_ending_check(tmp_path):
    ring = _wav(tmp_path / "quiet.wav", lambda s: 10 ** ((-22 - 3 * s) / 20), seconds=13.0)
    doc = _doc("It settles and decays to a quiet ending.")
    assert arc.fault(doc, ring) == [] and end_check.fault(doc, None, ring) == []
