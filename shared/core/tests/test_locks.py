"""The lock rule an agent relies on not breaking: it can't unlock what a person locked, and is told to ask them."""
import pytest

from rostrum_core import toy
from rostrum_core.errors import RostrumError
from rostrum_core.who import Who

SAM, CLAUDE = Who.person("sam"), Who.agent("claude-code")
LOCK, UNLOCK = ({"op": f"layer.{o}", "target": ["card"]} for o in ("lock", "unlock"))


def test_agent_cant_unlock_a_persons_lock_but_can_its_own():
    doc = toy.sample()
    doc.apply([LOCK], SAM)
    with pytest.raises(RostrumError) as e:
        doc.apply([UNLOCK], CLAUDE)
    assert "is locked by Sam" in str(e.value) and "ask Sam to unlock it" in str(e.value)
    assert doc.item("card")["locked"] is True
    doc.apply([UNLOCK], SAM)                                     # the person still can
    doc.apply([LOCK], CLAUDE)
    doc.apply([UNLOCK], CLAUDE)                                  # an agent's own lock it may lift
    assert doc.item("card")["locked"] is False
