"""The brief's words are read as the writer meant them: a negated phrase asks for nothing (a7: "(no build, no drop)"
read as asking for a build), and "the piano alone ends the piece" asks for an ending on fewer parts (a8)."""
from rostrum_sound import brief
from rostrum_sound.listen import squash  # noqa: F401  registers big_build


def test_a_negated_phrase_is_not_asked():
    assert brief.asks({"brief": "Steady energy all the way through (no build, no drop)"}, "big_build") is None
    assert brief.asks({"brief": "Don't build. Keep it level"}, "big_build") is None
    assert brief.asks({"brief": "It builds steadily to the peak"}, "big_build") == "It builds steadily to the peak"


def test_a_part_alone_at_the_end_asks_for_a_thin_ending():
    said = brief.asks({"brief": "After the peak: it falls away, and the piano alone ends the piece quietly"}, "thin_ending")
    assert said == "and the piano alone ends the piece quietly"
