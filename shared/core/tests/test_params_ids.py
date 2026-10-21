"""What agents rely on: a bad time or list value is refused loudly; group ids never repeat after a restart."""
import pytest

from rostrum_core import Document, Param, RostrumError, Who
from rostrum_core import toy
from rostrum_core.mcp.context import Groups


def test_bad_time_and_list_values_are_refused_not_clamped():
    t, gains = Param.time("at", max=10), Param.list("gains", "number", min=-60, max=12, max_items=3)
    assert t.check({"beats": 4}, "w") == {"beats": 4} and t.default == {"seconds": 0}
    assert gains.check([0, -6.5], "w") == [0, -6.5]
    for p, bad in [(t, 1.5), (t, {"seconds": 1, "beats": 2}), (t, {"secs": 1}), (t, {"seconds": -1}), (t, {"seconds": 11}),
                   (t, {"marker": ""}), (gains, [0, 99]), (gains, [1, 2, 3, 4]), (gains, "x"), (gains, [True])]:
        with pytest.raises(RostrumError):
            p.check(bad, "w")
    with pytest.raises(RostrumError, match=r"gains\[1\]"):
        gains.check([0, "loud"], "w")


def test_group_ids_stay_unique_after_a_restart(tmp_path):
    doc = toy.sample(tmp_path, "itm_card")
    agent = Who.agent("e2e-agent")
    first = Groups(idle_s=0).current(agent)
    doc.apply({"op": "layer.move", "target": ["card"], "args": {"x": 5}}, agent, session=first)
    doc.save()
    reopened = Document.open(tmp_path, "itm_card", toy.KIND)      # a new server process: new Groups, saved history
    again = Groups(idle_s=0, used=lambda: {c.session for c in reopened.history.changes}).current(agent)
    assert first == "e2e-agent-run-1" and again == "e2e-agent-run-2"
