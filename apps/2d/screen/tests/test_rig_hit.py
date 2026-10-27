"""A press on the rig in hand hits the part where it is drawn posed (hand maker C, C1: a raised arm, outside the rig's
box at rest, was missed and the rig unpicked)."""
from screen2d import rig_hit

RIG = {"bones": [{"id": "body", "parent": ""}, {"id": "upper", "parent": "body"}, {"id": "hand", "parent": "upper"}],
       "binds": [{"layer": "torso", "bone": "body"}, {"layer": "hand L", "bone": "hand"}, {"layer": "badge", "bone": ""}]}
ORDER = ["torso", "hand L", "badge"]
EDGES = {"torso": "M0 0L100 0L100 200L0 200Z", "hand L": "M300 -150L340 -150L340 -110L300 -110Z",   # raised, far off
         "badge": "M10 10L30 10L30 30L10 30Z"}


def test_a_raised_part_is_hit_where_it_is_drawn():
    assert rig_hit.press_target(RIG, ORDER, EDGES, [], 320, -130, on_rig_at_rest=False) == "hand"
    assert rig_hit.press_target(RIG, ORDER, EDGES, [], 50, 100, on_rig_at_rest=True) == "rig"     # the body: the rig moves
    assert rig_hit.press_target(RIG, ORDER, EDGES, [], 20, 20, on_rig_at_rest=True) == "rig"      # unbound: the rig moves
    assert rig_hit.press_target(RIG, ORDER, EDGES, [], 500, 500, on_rig_at_rest=False) == ""      # nothing of the rig there
    assert rig_hit.part_at(ORDER, EDGES, 20, 20) == "badge"                                        # topmost first
