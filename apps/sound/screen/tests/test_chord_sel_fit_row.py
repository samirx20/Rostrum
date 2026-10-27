"""What would break silently: the note panel's fields moving under a click (critic r12 should-fix 4, two wrong edits).
Fit to key is one button in its own place for every note selection in a song with a key, whether or not the notes are
outside the key, so the panel's rows never gain or lose a line as the selection changes."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rostrum_core import Who  # noqa: E402
from test_screen import bridge  # noqa: E402,F401  (the screen's fixture: a small song, a stand-in engine)


def _buttons(b):
    b.actions.refresh()
    return [i["id"] for r in b.actions.panel["rows"] for i in r["items"]]


def test_fit_to_key_is_always_in_the_notes_panel_row(bridge):  # noqa: F811
    bridge.doc.apply([{"op": "key.add", "target": [], "args": {"at": 0, "key": "C major"}},
                      {"op": "note.add", "target": ["lead"], "args": {"id": "lead.out", "pitch": "C#4", "at": {"beat": 20},
                                                                         "dur": {"beats": 1}}}], Who.person())
    bridge.selectMany(["lead.n2000"])                    # a note in the key
    inside = _buttons(bridge)
    bridge.selectMany(["lead.out"])                      # a note outside it
    outside = _buttons(bridge)
    assert inside == outside and "fit_key" in inside
