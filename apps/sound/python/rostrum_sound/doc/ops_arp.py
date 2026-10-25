"""`note.arpeggiate` (sound-pro-workflows SPEC § 3.11): Chord ▾ › Arpeggio…, each chord of the selection turned into
its tones one after another over the chord's own span, written as plain notes you can see and edit.

The stepping, the orders and the octaves are `writing/comp.py`'s (`stack`, `even_steps`, `play`): the same rule as the
script's arp(...). Each new note copies the chord note whose tone it plays (velocity and playing), its time and length
are written in that note's form, and its name is spelled in the key playing then (base C). The chord's notes are
removed in the same step, so one undo brings the chord back.
"""
from __future__ import annotations

import copy
import dataclasses

from rostrum_core import Param, codes

from ..writing.comp import ARP_MODES, even_steps, play, stack
from . import chords, ids, keys, tempo
from .registry import REGISTRY, taken
from .select_time import at_seconds, note_dur

MODES = [m for m in ARP_MODES if m != "chord"]
RATE = dataclasses.replace(Param.number("rate", min=1 / 32, max=1, default=0.25, group="Arpeggio", unit="beats",
                                        label="Rate", help="How long each step is, in beats: 0.25 = 16ths, 0.5 = 8ths, "
                                                           "1 = quarters, down to 1/32. A chord shorter than a step plays "
                                                           "one step."), step=1 / 32)
MODE = Param.choice("mode", MODES, default="up", group="Arpeggio", label="Pattern",
                    labels={"up": "Up", "down": "Down", "upDown": "Up and down", "downUp": "Down and up",
                            "converge": "Outside in", "diverge": "Inside out", "order": "As written", "random": "Random"},
                    help="The order of the tones: up, down, upDown, downUp, converge (outside in), diverge (inside out), "
                         "order (as written: a list's order, or separate notes by when they start), random (the same "
                         "every time for one seed).")
OCTAVES = Param.number("octaves", min=1, max=4, integer=True, default=1, group="Arpeggio", label="Octaves",
                       help="1 = the chord's own tones; 2 adds them an octave up, and so on.")
GATE = Param.number("gate", min=0.1, max=1, default=0.9, group="Arpeggio", importance="secondary", label="Gate",
                    display="percent", help="How much of each step a note holds: 1 = joined, 0.5 = short.")
SEED = Param.number("seed", min=0, max=1_000_000, integer=True, default=1, group="Arpeggio", importance="secondary",
                    label="Seed", help="Picks another random order; the same seed gives the same notes every time.")


@REGISTRY.operation("note.arpeggiate", "Turn each chord of the selection into its tones one after another, over the "
                    "chord's own span: a step every `rate` beats (0.25 = 16ths) in `mode` order (up, down, upDown, "
                    "downUp, converge, diverge, order = as written, random with `seed`), over `octaves` octaves, each "
                    "note holding `gate` of its step. The chord's notes are replaced by plain notes (one undo brings the "
                    "chord back); every new note lies inside the chord's span. Valid when the selection holds a chord of "
                    "two or more notes. The reply lists the removed and added notes. For a new part in a script, use "
                    "arp(...).", target="note", params=[RATE, MODE, OCTAVES, GATE, SEED], label="Arpeggio",
                    importance="secondary")
def arpeggiate(ctx, targets, args):
    rate, mode, octaves = args.get("rate", 0.25), args.get("mode", "up"), args.get("octaves", 1)
    gate, seed, root = args.get("gate", 0.9), args.get("seed", 1), ctx.doc
    plan = []
    for k, c in enumerate(chords.need_chords(ctx, targets)):
        if max(c["tones"]) + 12 * (octaves - 1) > 127:
            ctx.fail(codes.BAD_ARGUMENT, "octaves", f"{octaves} would go past the 128 notes", hint="Use fewer octaves.")
        notes = [ctx.item(t) for t in c["ids"]]
        source = {m: notes[0 if c["listed"] else i] for i, m in enumerate(c["tones"])}
        b0, b1 = tempo.beat_at(root, c["start"]), tempo.beat_at(root, c["end"])
        total = b1 - b0
        steps = even_steps(total, min(rate, total)) if total > 1e-6 else []
        run = play(steps, [stack(c["written"], octaves)], total, mode, lambda _, k=k: f"{seed}:{k}", gate)
        plan.append((c, [(_base(m[0], source), m[0], b0 + at, b0 + at + dur) for at, dur, m, _ in run]))
    for c, run in plan:                                  # all checked first: a failure changes nothing
        for t in c["ids"]:
            ctx.remove(t)
        for n, m, a, b in run:
            s, e = tempo.seconds_at(root, a), tempo.seconds_at(root, b)
            new = {f: copy.deepcopy(v) for f, v in n.items() if f not in ("id", "pitch", "at", "dur", "strum")}
            first = n["pitch"][0] if isinstance(n["pitch"], list) else n["pitch"]
            at = at_seconds(ctx, n, s)
            dur = note_dur(root, n, s, e)
            new.update(id=ids.note(c["track"], at, root, taken(ctx), ctx.where), at=at,
                       dur=round(e - s, 4) if dur is None else dur,
                       pitch=m if isinstance(first, int) else keys.pitch_name(m, keys.key_for(root, s)))
            ctx.insert(c["track"], "notes", new)


def _base(m: int, source: dict) -> dict:
    """The chord note whose tone `m` plays (`m` may be octaves above it)."""
    while m not in source:
        m -= 12
    return source[m]
