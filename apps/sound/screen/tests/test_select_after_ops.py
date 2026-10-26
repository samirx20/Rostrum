"""What would break silently: the selection after an action. What an action made in place of the selected notes is
selected (Arpeggio, then Humanise acts on every new note), and undoing a Duplicate leaves the originals selected, so
Ctrl+D again works (critic r10 should-fix 1 and 3)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rostrum_core import Who  # noqa: E402
from test_screen import bridge  # noqa: E402,F401  (the screen's fixture: a small song, a stand-in engine)


def _notes(b):
    return [n["id"] for n in b.doc.item("lead")["notes"]]


def test_the_notes_an_arpeggio_made_are_the_selection_and_undo_of_a_duplicate_keeps_the_originals(bridge):  # noqa: F811
    d = bridge.doc
    chord = [{"op": "note.add", "target": ["lead"], "args": {"id": f"lead.c{i}", "pitch": p, "at": {"beat": 8},
                                                               "dur": {"beats": 2}}} for i, p in enumerate(["C4", "E4", "G4"])]
    d.apply(chord, Who.person())
    old = ["lead.c0", "lead.c1", "lead.c2"]
    bridge.selectMany(old)
    bridge._act([{"op": "note.arpeggiate", "target": old, "args": {"rate": 0.5}}], "Arpeggio")
    after = list(bridge._picks.ids)
    assert len(after) >= 3 and not set(after) & set(old)
    assert set(after) <= set(_notes(bridge))                      # every selected id is a note of the song now
    assert set(_notes(bridge)) - set(after) == {"lead.n2000", "lead.n3000"}      # and every new note is selected

    bridge.selectMany(["lead.n2000"])
    bridge.run("duplicate")
    assert bridge._picks.ids != ["lead.n2000"]                    # the copy is selected
    bridge.undo()
    assert bridge._picks.ids == ["lead.n2000"]                    # the original is, so Ctrl+D works again
    assert bridge.run("duplicate")
