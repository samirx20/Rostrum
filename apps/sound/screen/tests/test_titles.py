"""A made-up id never reaches a title (tempo_1, pad.delay_1, drums.n1500); a person's own id still does."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from screensound.inspect import name_of


def test_made_up_ids_read_as_words():
    assert name_of({"id": "pad.delay_1", "type": "effect", "effect": "delay"}) == "Delay"
    assert name_of({"id": "pad.eq_2", "type": "effect", "effect": "eq"}) == "EQ"
    assert name_of({"id": "tempo_1", "type": "tempo"}) == "Tempo change"
    assert name_of({"id": "pad.auto_volume", "type": "lane"}) == "Automation"


def test_names_and_chosen_ids_stay():
    assert name_of({"id": "pad.delay_1", "type": "effect", "effect": "delay", "name": "Echo"}) == "Echo"
    assert name_of({"id": "pad", "type": "track"}) == "pad"


def test_master_and_old_section_names_read_as_words():
    assert name_of({"id": "master", "type": "master"}) == "Master"
    assert name_of({"id": "section.section_1", "type": "section", "name": "section_1"}) == "Section 1"
    assert name_of({"id": "section.verse", "type": "section", "name": "verse"}) == "verse"


def test_a_new_section_is_named_in_words():
    from screensound.song_edit import section_name as _name
    assert _name(set()) == "intro" and _name({"intro", "verse"}) == "chorus"
    assert "_" not in _name({"intro", "verse", "chorus", "bridge", "drop", "outro"})


def test_ids_in_a_status_line_become_names():
    from screensound.inspect import in_words

    class Doc:
        def items(self):
            return [self.item("track_1.c0")]

        def item(self, i):
            return {"id": i, "type": "clip", "media": "media/Take-1.wav"}
    assert in_words("track_1.c0: denoise 40%", Doc()) == "Take-1.wav: denoise 40%"
