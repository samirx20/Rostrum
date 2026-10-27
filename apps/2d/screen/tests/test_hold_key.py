"""Typing the value an animated field already shows, at a time with no key, writes a hold key (production round, hand #1):
before, it said "nothing changed" and the move started from the earlier key."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screen2d import route  # noqa: E402

BAR = {"id": "s", "type": "shape", "shape": "rect", "w": 100, "h": 10, "keys": [{"id": "k1", "prop": "h", "t": 0.3, "v": 10}]}


def test_same_value_on_animated_field_keys_a_hold():
    call = route.value_call(BAR, "h", 10, 2.5)
    assert call["op"] == "key.add" and call["args"]["t"] == 2.5 and call["args"]["v"] == 10


def test_still_field_and_key_here_unchanged():
    assert route.value_call({**BAR, "keys": []}, "h", 10, 2.5)["op"] == "value.set"
    assert route.value_call(BAR, "h", 10, 0.3)["op"] == "value.set"
