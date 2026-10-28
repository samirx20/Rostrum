"""A time written on a marker: a one-letter name keeps its offset ("#b+0.5" is b, not a marker named "b+0.5")."""
import pytest

from rostrum_core import marker_times as mt


@pytest.mark.parametrize("text,want", [
    ("#b+0.5", ("b", 0.5)), ("#b-1", ("b", -1)), ("#b", ("b", 0)),
    ("#big-hit-1", ("big-hit", -1)), ("#logo lands+0.5", ("logo lands", 0.5)), ("#drop - 2", ("drop", -2)),
])
def test_split_reads_name_and_offset(text, want):
    assert mt.split(text) == want


def test_seconds_adds_the_offset_to_a_one_letter_marker():
    assert mt.seconds("#b+0.5", {"b": 4.0}, "at") == 4.5
