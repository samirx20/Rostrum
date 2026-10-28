"""A second script name that re-makes another script's tracks is refused, naming the script to run under."""
import pytest

from rostrum_core import RostrumError
from rostrum_sound.mcp.script_twins import refuse_second_copy
from rostrum_sound.script import run_source


class Doc:
    def __init__(self, bases):
        self.script_bases, self.data = bases, {}
        from rostrum_sound import KIND
        self.kind = KIND


SRC = "tempo(96); length(bar(3)); t = track('keys', builtIn='piano'); t.note('C4', at=bar(1), dur=beats(4))"


def test_new_name_on_the_same_tracks_is_refused():
    doc = Doc({"cue": run_source(SRC, "cue")})
    with pytest.raises(RostrumError, match='"cue"'):
        refuse_second_copy(doc, {"name": "cue2", "source": SRC})
    refuse_second_copy(doc, {"name": "cue", "source": SRC})                      # the same name replaces: fine
    other = "t = track('bells', builtIn='glockenspiel'); t.note('C6', at=bar(2), dur=beats(1))"
    refuse_second_copy(doc, {"name": "bells", "source": other})                 # new tracks beside it: fine
