"""A made-up id never reaches a title (tempo_1, pad.delay_1, drums.n1500); a person's own id still does."""
from screensound.inspect import name_of


def test_made_up_ids_read_as_words():
    assert name_of({"id": "pad.delay_1", "type": "effect", "effect": "delay"}) == "Delay"
    assert name_of({"id": "pad.eq_2", "type": "effect", "effect": "eq"}) == "EQ"
    assert name_of({"id": "tempo_1", "type": "tempo"}) == "Tempo change"
    assert name_of({"id": "pad.auto_volume", "type": "lane"}) == "Automation"


def test_names_and_chosen_ids_stay():
    assert name_of({"id": "pad.delay_1", "type": "effect", "effect": "delay", "name": "Echo"}) == "Echo"
    assert name_of({"id": "pad", "type": "track"}) == "pad"
