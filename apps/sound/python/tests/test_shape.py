"""t.shape writes plain values into the tree (velocities, a note's dynamics, one lowpass EQ, articulations): a curve
applied wrong, twice, or differently on a re-run would only be heard."""
import pytest
from rostrum_core import RostrumError

from rostrum_sound import run_source

SONG = """
tempo(60)
s = track("s", sfz=r"C:\\\\x\\\\main.sfz", articulations={"trem": r"C:\\\\x\\\\trem.sfz"})
for i in range(8):
    s.note("C4", at=beat(i), dur=beats(1), vel=0.5)
s.note("G4", at=beat(2), dur=beats(4), vel=0.5)
s.shape("vol", 1.0, 2.0, over=(beat(2), beat(6)))
s.shape("art", "", "trem", over=(beat(0), beat(4)))
s.shape("bright", 0, 1, over=(beat(0), beat(4)), curve="late")
s.shape("bright", 0.5, 1, over=(beat(5), beat(7)))
s.humanize(seed=3, timing=0, velocity=0)
"""


def _track(src=SONG):
    tree = run_source(src, "song.py")
    return next(t for t in tree["tracks"] if t["id"] == "s")


def _notes(t):
    return {(n["at"]["beat"], n["pitch"]): n for n in t["notes"]}


def test_vol_multiplies_along_the_span_and_holds_after():
    n = _notes(_track())
    assert [n[(b, "C4")]["vel"] for b in range(8)] == [0.5, 0.5, 0.5, 0.625, 0.75, 0.875, 1.0, 1.0]


def test_a_held_note_swells_inside_itself():
    n = _notes(_track())
    assert n[(2, "G4")]["dynamics"] == [[0, 1.0], [1, 2.0]]      # 1.0 at its start, 2.0 at its end
    assert "dynamics" not in n[(3, "C4")]                         # a one-beat note is not held


def test_bright_is_one_lowpass_with_an_envelope():
    t = _track()
    eqs = [e for e in t["effects"] if e["effect"] == "eq"]
    assert len(eqs) == 1 and eqs[0]["id"] == "s.eq_bright"
    band, = eqs[0]["bands"]
    assert band["shape"] == "lowpass" and isinstance(band["freq"], list)
    times = [p[0] for p in band["freq"]]
    assert times == sorted(times) and len(set(times)) == len(times)
    assert band["freq"][0] == [0.0, 250.0] and band["freq"][-1][1] == 20000.0
    held = [p for p in band["freq"] if 4 <= p[0] <= 5]                # between the shapes: the first one's end, held
    assert [p[1] for p in held] == [20000.0, 20000.0]


def test_art_switches_where_the_curve_passes_its_middle():
    n = _notes(_track())
    assert [n[(b, "C4")].get("art", "") for b in range(5)] == ["", "", "trem", "trem", "trem"]


def test_a_rerun_gives_the_same_tree():
    assert run_source(SONG, "song.py") == run_source(SONG, "song.py")


def test_wrong_names_are_loud():
    for line in ('s.shape("art", "", "pizz", over=(0, 1))', 's.shape("vol", 0, 1, over=(0, 1), curve="ease")',
                 's.shape("loud", 0, 1, over=(0, 1))'):
        with pytest.raises(RostrumError):
            run_source(SONG + line, "song.py")
