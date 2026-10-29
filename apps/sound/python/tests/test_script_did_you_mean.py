"""A wrong name, call or argument in a Sound script names the closest real ones at its line, and nothing is applied."""
import pytest
from rostrum_core import RostrumError

from rostrum_sound import run_source


def _error(source):
    with pytest.raises(RostrumError) as e:
        run_source(source, "s1")
    return e.value.line()


def test_wrong_names_say_the_close_ones():
    assert _error('trak("a")').endswith("Did you mean track?")
    assert _error('drums = track("a")\ndrum.hit()').endswith("Did you mean drums?")
    assert "line 2: track.nots" in _error('t = track("a")\nt.nots([])')
    assert _error('t = track("a")\nt.nots([])').endswith("Did you mean note?")
