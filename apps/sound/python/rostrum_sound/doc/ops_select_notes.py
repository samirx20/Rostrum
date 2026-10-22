"""Edits for the selected notes and drum hits: quantize (snap to a grid), humanize (a little looseness, the same
every run), and transpose (notes only; a chord moves together). Each is one operation over the selection, so one
undo step. A time keeps its form: beats stay beats, a marker time keeps its marker (see `select_time.py`).
"""
from __future__ import annotations

import random

from rostrum_core import Param, codes

from . import keys, tempo
from . import values as V
from .registry import REGISTRY
from .select_time import at_seconds, end_of, start_of

N = V.N
GRID = N("grid", 0.0625, 16, "Quantize", "beats", default=0.25, label="Grid",
         help="The grid to snap to, in beats: 1 = a beat, 0.5 = eighths, 0.25 = sixteenths. Left out = 0.25.")
STRENGTH = N("strength", 0, 1, "Quantize", default=1, label="Strength", display="percent",
             help="0 = leave as played, 1 = exactly on the grid, in between = part of the way. Left out = 1.")
ENDS = Param.toggle("ends", group="Quantize", label="Snap the ends too", importance="secondary",
                    help="Notes only: the end of each note snaps to the grid as well (its length changes).")
TIMING = N("timing", 0, 200, "Humanize", "ms", default=10, label="Timing", help="Each start moves by up to this "
          "many milliseconds, earlier or later. Left out = 10.")
VELOCITY = N("velocity", 0, 1, "Humanize", default=0.05, label="Velocity", display="percent",
             help="Each velocity changes by up to this much (0 … 1 scale). Left out = 0.05.")
SEED = N("seed", 1, 999999, "Humanize", imp="secondary", integer=True, default=1, label="Seed",
         help="The same seed on the same notes gives the same result every time; another seed, another feel.")
SEMITONES = Param.number("semitones", min=-48, max=48, integer=True, required=True, group="Transpose", unit="st",
                         label="Semitones", help="How far up (+) or down (−), in half steps; 12 = an octave. A "
                                                 "chord moves together.")
LABELS = {"note": "note", "hit": "drum hit"}


def _snap(root, sec, grid, strength):
    b = tempo.beat_at(root, sec)
    return tempo.seconds_at(root, b + (round(b / grid) * grid - b) * strength)


def _new_length(root, item, start, new_start, new_end):
    """The note's `dur` for its new end, written like the old one (seconds or beats); None for a tied length."""
    dur = item["dur"]
    if dur == "next" or (isinstance(dur, dict) and "to" in dur):
        return None
    if isinstance(dur, dict):
        return {"beats": round(tempo.beat_at(root, new_end) - tempo.beat_at(root, new_start), 4)}
    return round(new_end - new_start, 4)


def _quantize(kind):
    @REGISTRY.operation(f"{kind}.quantize", f"Snap the selected {LABELS[kind]}s to a grid (in beats), all the way "
                        "or part of the way." + (" Optionally the ends too." if kind == "note" else ""),
                        target=kind, params=[GRID, STRENGTH, *([ENDS] if kind == "note" else [])],
                        label=f"Quantize {LABELS[kind]}s")
    def quantize(ctx, targets, args):
        root, grid, strength = ctx.doc, args.get("grid", 0.25), args.get("strength", 1)
        plan = []
        for t in targets:
            item = ctx.item(t)
            start = start_of(root, item)
            new = _snap(root, start, grid, strength)
            plan.append((t, "at", at_seconds(ctx, item, new)))
            if args.get("ends") and kind == "note":
                end = _snap(root, end_of(root, item), grid, strength)
                if end <= new + 1e-6:
                    end = tempo.seconds_at(root, tempo.beat_at(root, new) + grid)
                length = _new_length(root, item, start, new, end)
                if length is not None:
                    plan.append((t, "dur", length))
        for t, k, v in plan:
            ctx.set(t, k, v)


def _humanize(kind):
    @REGISTRY.operation(f"{kind}.humanize", f"Make the selected {LABELS[kind]}s a little looser: tiny changes to "
                        "when they start and how hard they play. The same seed gives the same result.",
                        target=kind, params=[TIMING, VELOCITY, SEED], label=f"Humanize {LABELS[kind]}s")
    def humanize(ctx, targets, args):
        root, ms, vel = ctx.doc, args.get("timing", 10), args.get("velocity", 0.05)
        for t in targets:
            item, rnd = ctx.item(t), random.Random(f'{args.get("seed", 1)}:{t}')
            dt, dv = rnd.uniform(-ms, ms) / 1000, rnd.uniform(-vel, vel)
            if ms:
                ctx.set(t, "at", at_seconds(ctx, item, start_of(root, item) + dt))
            if vel:
                ctx.set(t, "vel", round(min(1.0, max(0.0, item.get("vel", 0.8) + dv)), 4))


for _kind in LABELS:
    _quantize(_kind)
    _humanize(_kind)


def _shifted(p, by):
    k = keys.midi(p) + by
    if not 0 <= k <= 127:
        raise ValueError(k)
    if isinstance(p, int):
        return k
    return keys.pitch_name(k, "F major" if "b" in p[1:2] else None)       # keep flats a flat note was written with


@REGISTRY.operation("note.transpose", "Move the selected notes up or down in half steps (12 = an octave); a "
                    "chord moves together.", target="note", params=[SEMITONES], label="Transpose")
def transpose(ctx, targets, args):
    by = args["semitones"]
    for t in targets:
        pitch = ctx.item(t)["pitch"]
        try:
            new = [_shifted(p, by) for p in pitch] if isinstance(pitch, list) else _shifted(pitch, by)
        except ValueError:
            ctx.fail(codes.BAD_ARGUMENT, f'"{t}"', f"would go outside the 128 notes by {by:+d} half steps",
                     hint="Transpose by less.")
        ctx.set(t, "pitch", new)
