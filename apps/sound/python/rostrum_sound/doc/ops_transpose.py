"""`note.transpose`: the selected notes up or down by half steps (`semitones`) or by steps of the song's key (`steps`,
the key playing at each note's own time; a chord moves by its lowest note's step, so it keeps its shape). One rule for
the screen's Transpose menu, Ctrl+↑ / ↓ and agents. Going past the 128 notes fails and changes nothing.
"""
from __future__ import annotations

from rostrum_core import Param, codes

from . import keys
from .registry import REGISTRY
from .select_time import start_of

SEMITONES = Param.number("semitones", min=-48, max=48, integer=True, group="Transpose", unit="semitones",
                         label="Semitones", help="How far up (+) or down (−), in half steps; 12 = an octave, 7 = a fifth. "
                                                 "A chord moves together. Give this or `steps`.")
STEPS = Param.number("steps", min=-14, max=14, integer=True, group="Transpose", unit="steps", label="Steps",
                     help="How far up (+) or down (−), in steps of the song's key at each note (2 = a third, 4 = a fifth, "
                          "7 = an octave in a 7-note key), so the notes stay in the key. Give this or `semitones`.")
NO_KEY = "The song has no key: set one in the key picker, or transpose in half steps"


def _shifted(p, by, key=None):
    k = keys.midi(p) + by
    if not 0 <= k <= 127:
        raise ValueError(k)
    if isinstance(p, int):
        return k
    if key:
        return keys.pitch_name(k, key)                                      # along the key: the key's spelling
    return keys.pitch_name(k, "F major" if "b" in p[1:2] else None)         # keep flats a flat note was written with


def _distance(ctx, t, pitch, steps) -> tuple[int, str]:
    """(half steps, key) for moving this note `steps` along the key at its time."""
    key = keys.key_for(ctx.doc, start_of(ctx.doc, ctx.item(t)))
    if not key:
        ctx.fail(codes.BAD_ARGUMENT, "steps", NO_KEY, hint='Set a key (key.add {at: 0, key: "D minor"}) or give `semitones`.',
                 plain=NO_KEY + ".")
    lowest = min(keys.midis(pitch))
    return keys.steps_in_key(lowest, key, steps) - lowest, key


@REGISTRY.operation("note.transpose", "Move the selected notes up or down: `semitones` in half steps (12 = an octave), "
                    "or `steps` along the song's key at each note (2 = a third up; a chord moves by its lowest note's "
                    "step). Exactly one of the two. Past the 128 notes it fails and changes nothing.",
                    target="note", params=[SEMITONES, STEPS], label="Transpose")
def transpose(ctx, targets, args):
    given = [k for k in ("semitones", "steps") if k in args]
    if len(given) != 1:
        ctx.fail(codes.BAD_ARGUMENT, "arguments", f"name {' and '.join(given) or 'neither semitones nor steps'}: "
                 "give exactly one", ["{semitones: 7}", "{steps: 2}"])
    plan = []
    for t in targets:
        pitch = ctx.item(t)["pitch"]
        by, key = (args["semitones"], None) if given == ["semitones"] else _distance(ctx, t, pitch, args["steps"])
        try:
            new = [_shifted(p, by, key) for p in pitch] if isinstance(pitch, list) else _shifted(pitch, by, key)
        except ValueError:
            ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', f"would go outside the 128 notes by {by:+d} half steps",
                     hint="Transpose by less.")
        plan.append((t, new))
    for t, new in plan:                                  # all checked first: a failure changes nothing
        ctx.set(t, "pitch", new)
