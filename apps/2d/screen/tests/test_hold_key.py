"""Typing the value an animated field already shows, at a time with no key, writes a hold key (production round, hand #1):
before, it said "nothing changed" and the move started from the earlier key."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screen2d import route  # noqa: E402

BAR = {"id": "s", "type": "shape", "shape": "rect", "w": 100, "h": 10, "keys": [{"id": "k1", "prop": "h", "t": 0.3, "v": 10}]}


class _Doc:
    def item(self, _id):
        return BAR


def test_same_value_on_animated_field_keys_a_hold():
    call = route.edit_call(_Doc(), "s", "h", 10, 2.5)
    assert call["op"] == "key.add" and call["args"]["t"] == 2.5 and call["args"]["v"] == 10


def test_still_field_and_key_here_unchanged():
    assert route.value_call({**BAR, "keys": []}, "h", 10, 2.5)["op"] == "value.set"
    assert route.edit_call(_Doc(), "s", "h", 10, 0.3)["op"] == "value.set"


def test_key_mark_on_an_animated_field_still_keys():
    """The key diamond goes through value_call too: it must stay a plain key.add (hand #6, a KeyError)."""
    calls, _ = route.animate_calls(BAR, "h", 2.5, 30)
    assert calls[0]["op"] == "key.add" and calls[0]["args"]["t"] == 2.5
