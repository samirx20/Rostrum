"""What would break silently: the selection after the Chord helpers (critic r12 should-fix 5). Make a chord leaves the
whole chords selected (so Arpeggio… is offered at once), and after Arpeggio… (the popover's own session) every new
note is selected, so Humanise acts on all of them."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_screen import bridge  # noqa: E402,F401  (the screen's fixture: a small song, a stand-in engine)


def test_make_a_chord_selects_the_chords_and_arpeggio_selects_every_new_note(bridge):  # noqa: F811
    roots = ["lead.n2000", "lead.n3000"]
    bridge.selectMany(roots)
    assert bridge.run("chord_major")
    chords = list(bridge._picks.ids)
    assert set(roots) < set(chords) and len(chords) == 6                    # the roots and their two other tones each

    assert bridge.actions.ask("arpeggio")
    bridge.actions.amounts.keep()
    after = list(bridge._picks.ids)
    assert len(after) > len(chords)                                         # more notes than the chords had
    assert set(after) <= {n["id"] for n in bridge.doc.item("lead")["notes"]}
    assert not set(after) & {"lead.n2000_2", "lead.n3000_3"}               # none of the old chord notes is left selected
