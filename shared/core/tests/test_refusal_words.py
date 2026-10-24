"""A refusal says what is missing in the plain words people and agents read, never an internal fact name."""
from rostrum_core.conditions import FACTS, describe


def test_refusal_reads_in_plain_words():
    cond = {"all": [{"fact": "underCamera"}, {"not": {"is": ["locked", True]}}]}
    assert describe(cond) == "it sits directly in a scene (not in a group) and Locked is off"
    assert describe(cond, {"locked": "Lock"}) == "it sits directly in a scene (not in a group) and Lock is off"
    assert "underCamera" not in describe({"fact": "somethingNew"}) and describe({"fact": "somethingNew"}) == "something new"


def test_a_negated_fact_has_its_own_words():
    assert describe({"not": {"fact": "frameAway"}}) == FACTS["frameAway"][1]
