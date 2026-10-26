"""A section owns its notes by their musical place (critic r10 must-fix 2): a drum hit Humanise nudged a hair before a
section line belongs to the section it opens, so section.duplicate copies it and section.move takes it along, and
one a hair before a section's end stays with the next section. Plus Repeat's step (must-fix 7): whole bars from the
bar line at or before the first note, for any length."""
import pytest
from rostrum_core import Document, RostrumError, Who

from rostrum_sound import KIND
from rostrum_sound.doc import meter

P = Who.person()


def _op(op, target, **args):
    return {"op": op, "target": target, "args": args}


def _hits(d):
    return sorted(round(h["at"]["beat"], 3) for h in d.item("k")["hits"])


def _song(sections, beats):
    """120 bpm (a beat = 0.5 s), a kit with a hit on each of `beats`, and `sections` [(name, start beat, end beat)]."""
    d = Document.new(KIND)
    d.apply([_op("doc.set", ["root"], tempo=120), _op("track.add", [], id="k", instrument="kit", kit="drums"),
             *[_op("hit.add", ["k"], id=f"h{i}", drum="hat", at={"beat": b}) for i, b in enumerate(beats)],
             *[_op("section.add", [], name=n, at=a / 2, end=b / 2) for n, a, b in sections]], P)
    return d


def test_duplicate_copies_the_nudged_first_hit_and_is_not_refused_by_the_next_sections():
    # verse 0–8, gap, chorus 16–24; the verse's first hit at 0, the chorus's first nudged to 15.99
    d = _song([("verse", 0, 8), ("chorus", 16, 24)], [0, 2, 4, 6, 15.99, 18])
    d.apply(_op("section.duplicate", ["section.verse"]), P)                 # the copy fills 8–16, up to the chorus
    assert _hits(d) == [0, 2, 4, 6, 8, 10, 12, 14, 15.99, 18]


def test_duplicate_chorus_takes_its_early_hit_and_leaves_the_next_sections():
    d = _song([("verse", 0, 8), ("chorus", 8, 16)], [0, 4, 7.99, 12])
    d.apply(_op("section.duplicate", ["section.chorus"]), P)
    assert _hits(d) == [0, 4, 7.99, 12, 15.99, 20]                          # the chorus owns 7.99 and 12, copied 8 later
    assert [s["name"] for s in d.data["sections"]] == ["verse", "chorus", "chorus-2"]


def test_duplicate_is_refused_by_a_hit_opening_the_bars_after():
    d = _song([("verse", 0, 8), ("chorus", 8, 16)], [0, 7.99, 12, 15.99])  # 15.99 opens the bars after the chorus
    with pytest.raises(RostrumError, match="1 drum hit"):
        d.apply(_op("section.duplicate", ["section.chorus"]), P)


def test_move_takes_the_nudged_hits_along_and_nothing_of_the_next_section():
    d = _song([("break", 0, 8), ("outro", 8, 16), ("tail", 16, 24)], [0, 7.99, 12, 15.99, 20])
    d.apply(_op("section.move", ["section.outro"], by={"beats": 8}), P)
    assert _hits(d) == [0, 15.99, 15.99, 20, 20]                            # 7.99 and 12 went; the tail's 15.99 stayed


@pytest.mark.parametrize("start, end, single, step", [
    (0, 13, False, 16),          # four quarter chords on bars 1–4: the copy starts at bar 5
    (6, 14, False, 8),           # an 8-beat phrase from bar 2 beat 3: right after itself, same beat (no one-bar hole)
    (4, 6.25, False, 4),         # two claps on bar 2 beats 1 and 3 (the second fills one grid cell): the next bar
    (24, 26, False, 4),          # a 2-beat phrase on bar 7 beats 1–2: bar 8 beats 1–2
    (5, 6, True, 1),             # one quarter note: the next beat (a run)
    (18, 19, False, 1),          # a 1-beat fill (two 8ths): the next beat
    (4, 4.25, True, 0.25),       # one drum hit: the next grid cell
    (0, 3, True, 3),             # one 3-beat note: its own length
    (31.99, 45, False, 16),      # humanised first chord: still 4 bars
])
def test_copy_step_counts_from_the_first_note(start, end, single, step):
    """Critic r11 must-fix 3: Ctrl+D's step (beats; 120 bpm, so seconds = beats / 2)."""
    assert meter.copy_step({"tempo": 120}, start / 2, end / 2, 0.25, single) == pytest.approx(step)


def test_copy_step_reads_the_time_signature():
    assert meter.copy_step({"tempo": 120, "beatsPerBar": 3}, 0.0, 4 / 2) == pytest.approx(6)
