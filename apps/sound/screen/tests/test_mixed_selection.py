"""Select all, then a key: the actions reach the part of a mixed selection they can take, and ← at the song's start
is a plain refusal, never an exception (critic r6 must-fix 6: "note.move failed: StopIteration", a false
"Quantise needs notes or drum hits selected" on 178 notes + 202 hits). No Qt."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rostrum_core import Document, RostrumError, Who  # noqa: E402
from rostrum_sound import KIND  # noqa: E402
from screensound import action_calls as C  # noqa: E402
from screensound.actions import ACTIONS  # noqa: E402

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def _song():
    d = Document.new(KIND)
    d.apply([_op("track.add", [], id="a", instrument="builtIn", builtIn="feltPiano"),
             _op("track.add", [], id="k", instrument="kit", kit="classic"),
             _op("note.add", ["a"], id="n", pitch="C4", at={"beat": 0.1}, dur=1),
             _op("note.add", ["a"], id="m", pitch="E4", at={"beat": 2.1}, dur=1),
             _op("hit.add", ["k"], id="h", drum="kick", at={"beat": 1.1}),
             _op("marker.add", [], id="drop", name="drop", at=4)], P)
    return d


def test_a_mixed_selection_reaches_quantise_and_transpose():
    d = _song()
    f = C.Facts(d, ["a", "n", "m", "h", "drop"])                     # Select all: a track, notes, a hit, a marker
    act = {a["key"]: a for a in ACTIONS}
    for key in ("quantize", "transpose_up"):
        assert act[key]["valid_when"](f), key
    d.apply(act["quantize"]["calls"](f), P)
    assert d.item("n")["at"] == {"beat": 0.0} and d.item("h")["at"] == {"beat": 1.0}
    assert f.words(("note", "hit")) == "2 notes and 1 drum hit"
    assert not act["quantize"]["valid_when"](C.Facts(d, ["a", "drop"]))     # none of them can: refused, with its reason


def test_a_nudge_at_the_start_refuses_and_a_near_one_keeps_the_spacing():
    d = _song()
    f = C.Facts(d, ["n", "m", "h"])
    d.apply(C.nudge(f, -0.25), P)                                     # 0.1 beats from the start: the block goes to 0
    assert d.item("n")["at"] == {"beat": 0.0} and d.item("h")["at"] == {"beat": 1.0} and d.item("m")["at"] == {"beat": 2.0}
    assert C.nudge(C.Facts(d, ["n", "m", "h"]), -0.25) == []          # already there: the key refuses in words
    with pytest.raises(RostrumError) as e:                            # an agent's note.move before 0: words, not a crash
        d.apply(_op("note.move", ["n"], by={"beats": -1}), P)
    assert e.value.code == "BAD_ARGUMENT" and "StopIteration" not in e.value.person()
