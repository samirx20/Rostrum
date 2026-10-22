"""The velocity strip's gestures: relative drag, Alt, a line across (screensound/velocity.py)."""
from screensound import velocity as V

GRABS = [{"id": "a", "type": "note", "t": 0.0, "vel": 0.8}, {"id": "b", "type": "note", "t": 1.0, "vel": 0.4},
         {"id": "c", "type": "note", "t": 2.0, "vel": 0.6}]


def vels(calls):
    return {c["target"][0]: c["args"]["vel"] for c in calls}


def test_bar_drag_keeps_the_proportions():
    assert vels(V.bar_calls(GRABS, "a", 0.4)) == {"a": 0.4, "b": 0.2, "c": 0.3}


def test_alt_sets_all_to_one_height():
    assert set(vels(V.bar_calls(GRABS, "b", 0.5, alt=True)).values()) == {0.5}


def test_line_changes_only_notes_under_it():
    assert vels(V.line_calls(GRABS, 0.0, 0.2, 2.0, 1.0)) == {"a": 0.2, "b": 0.6, "c": 1.0}
    assert vels(V.line_calls(GRABS, 0.5, 0.2, 1.5, 1.0)) == {"b": 0.6}
