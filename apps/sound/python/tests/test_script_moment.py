"""A script's moment(...): rest / stop / strike edit the notes the script wrote, the same on every run."""
import pytest

from rostrum_core import RostrumError
from rostrum_sound import run_source
from rostrum_sound.script_scope import printed

SRC = """tempo(120); length(40)
bed = track("bed", builtIn="grandPiano")
for i in range(16):
    bed.note("C3", at=28.0 + i * 0.5, dur=beats(2))        # every 0.5 s, each 1 s long (beats at 120 bpm)
bed.note("E3", at=20.0, dur=13.0)                          # rings across the whole moment (seconds)
d = track("drums", kit="drums")
for i in range(24):
    d.hit("kick", at=28.0 + i * 0.5)
m = moment("hit", at=31.5)
m.rest(bed, before=0.5)
m.stop(d, until=34.0)
m.strike(bed, ["C2", "G2"], vel=1.0, ring=3.0)
m.strike(d, "crash", vel=1.0)
"""


def _secs(at):
    return at if isinstance(at, (int, float)) else at["beat"] * 0.5


def test_rest_stop_and_strike_edit_the_written_notes_the_same_every_run():
    tree = run_source(SRC, "t.py")
    bed, drums = tree["tracks"]
    assert any(m["name"] == "hit" and m["at"] == 31.5 for m in tree["markers"])
    starts = sorted(_secs(n["at"]) for n in bed["notes"])
    assert not [s for s in starts if 31.0 <= s < 31.5]                      # the breath: nothing starts in it
    held = {_secs(n["at"]): n["dur"] for n in bed["notes"] if n["pitch"] == "E3"}
    assert held == {20.0: 11.0}                                             # seconds stay seconds, cut at 31.0
    c3 = {_secs(n["at"]): n["dur"] for n in bed["notes"] if n["pitch"] == "C3"}
    assert c3[30.5] == {"beats": 1.0} and c3[30.0] == {"beats": 2}          # beats stay beats, cut at 31.0
    strike = [n for n in bed["notes"] if isinstance(n["pitch"], list)]
    assert len(strike) == 1 and strike[0]["at"] == 31.5 and strike[0]["dur"] == 3.0
    hits = sorted((_secs(h["at"]), h["drum"]) for h in drums["hits"])
    assert (31.5, "crash") in hits and (31.5, "kick") in hits                # on the moment plays
    assert not [t for t, _ in hits if 31.53 < t < 34.0]                     # a real gap, not quieter
    assert (34.0, "kick") in hits
    reply = printed()
    assert any(line.startswith("moment hit at 31.50 s: rest 0.50 s on bed (") for line in reply), reply
    assert run_source(SRC, "t.py") == tree


def test_wrong_arguments_name_the_right_form():
    with pytest.raises(RostrumError, match="before=0.4"):
        run_source(SRC + "m.rest('bed', before=0.4)", "t.py")
    with pytest.raises(RostrumError, match="ring="):
        run_source(SRC + "m.strike(bed, 'C4')", "t.py")
