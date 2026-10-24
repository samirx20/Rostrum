"""A pair (Position X | Y) is one setting: its one key mark keys both halves as ONE change and shows their joint state
(pairs.py, bridge.toggleAnimate; the inventory's worst #3: the diamond keyed X alone and the shape jumped in Y)."""
from rostrum_gui import pairs


def test_the_pair_mark_says_both_halves_and_the_bridge_finds_the_partner():
    static = pairs.pair_up([{"row": "param", "id": "x", "label": "X", "type": "number"},
                            {"row": "param", "id": "y", "label": "Y", "type": "number"}])
    assert static[0]["label"] == "Position" and pairs.partner_of(static, "y") == ["x", "y"]
    assert pairs.partner_of(static, "opacity") == ["opacity"]
    assert pairs.both_anim("onkey", "onkey") == "onkey" and pairs.both_anim("keyed", "still") == "keyed"
    assert pairs.both_anim("still", "still") == "still" and pairs.both_anim("onkey", "keyed") == "keyed"
