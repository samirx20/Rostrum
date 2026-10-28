"""build_to writes a build into a moment as plain notes tied to the target (3E audit R7): moving the marker moves the
whole build, the roll gets denser and louder, and a mix of beats and seconds is refused, never guessed."""
import pytest
from rostrum_core import RostrumError

from rostrum_sound import run_source

BUILD = '''tempo(120); length(bar(12)); marker("impact", at=bar(9))
d = track("drums", kit="drums"); s = track("str", builtIn="strings"); low = track("low", builtIn="piano")
build_to("#impact", over=beats(8), parts=[cymbal_roll(d), crescendo(s, ["D3", "A3"]), sub_hit(low, "D1"), sub_hit(d, "kick")])'''


def _track(tree, id_):
    return next(t for t in tree["tracks"] if t["id"] == id_)


def test_the_build_is_plain_notes_on_the_marker():
    tree = run_source(BUILD, "b.py")
    hits = [h for h in _track(tree, "drums")["hits"] if h["drum"] == "cymbal"]
    gaps = [float(h["at"][len("#impact"):-len("beats")]) for h in hits]
    assert gaps[0] == -8 and all(-8 <= g < 0 for g in gaps)                  # from 8 beats before, never on the target
    assert hits[-1]["vel"] > hits[0]["vel"] and (gaps[-1] - gaps[-2]) < (gaps[1] - gaps[0])    # louder, denser
    held = _track(tree, "str")["notes"][0]
    assert held["at"] == "#impact-8beats" and held["dur"] == {"to": "#impact"} and held["dynamics"][-1][1] > held["dynamics"][0][1]
    assert _track(tree, "low")["notes"][0]["at"] == "#impact"
    assert any(h["drum"] == "kick" and h["at"] == "#impact" for h in _track(tree, "drums")["hits"])


def test_a_bar_target_stays_on_the_grid_and_seconds_on_a_bar_are_refused():
    tree = run_source('tempo(120); length(bar(12)); s = track("str", builtIn="strings")\n'
                      'build_to(bar(9), over=beats(4), parts=[reverse_swell(s, "D5")])', "c.py")
    note = tree["tracks"][0]["notes"][0]
    assert note["at"] == {"beat": 28.0} and note["dur"] == {"to": {"beat": 32.0}} and note["dynamics"][0][1] == 0
    with pytest.raises(RostrumError, match="beats"):
        run_source('s = track("str", builtIn="strings"); build_to(bar(9), over=3, parts=[crescendo(s, "D3")])', "d.py")
