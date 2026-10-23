"""A group left with one of several members gives up its heading and joins the group above."""
from rostrum_gui import rows


def _row(id_, group, holds=True):
    return {"row": "param", "id": id_, "group": group, "holds": holds, "valid": holds}


def test_lone_leftover_joins_the_group_above():
    r = [{"row": "group", "id": "group:A", "label": "A", "members": ["a", "b"], "holds": True}, _row("a", "A"), _row("b", "A"),
         {"row": "group", "id": "group:Mix", "label": "Mix", "members": ["v", "p", "tone"], "holds": True},
         _row("v", "Mix"), _row("p", "Mix"), _row("tone", "Mix")]
    out = rows.omit(r, {"v", "p"})
    assert [x["id"] for x in out] == ["group:A", "a", "b", "tone"]
    assert out[0]["members"] == ["a", "b", "tone"] and out[-1]["group"] == "A"
