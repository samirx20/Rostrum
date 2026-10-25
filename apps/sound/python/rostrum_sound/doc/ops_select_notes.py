"""Edits for the selected notes and drum hits: quantize (snap to a grid), humanize (a little looseness, the same
every run). Transpose is `ops_transpose.py`. Each is one operation over the selection, so one
undo step. A time keeps its form: beats stay beats, a marker time keeps its marker (see `select_time.py`).
"""
from __future__ import annotations

import random

from rostrum_core import Param

from . import meter, tempo
from . import values as V
from .registry import REGISTRY
from .select_time import at_seconds, end_of, note_dur, start_of

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
SWING = N("swing", 0, 1, "Quantize", default=0, label="Swing", display="percent",
          help="The off-beat grid lines move late by swing × grid / 3 (1 = a triplet feel, like the track feel's swing) and "
               "everything snaps to them; on-beat lines stay. Left out = 0 (straight).")
LENGTH = N("length", 0, 0.5, "Humanize", default=0, label="Length", display="percent",
           help="Notes only: each note's length changes by up to this share of itself (0.1 = ±10 %). Left out = 0.")
LABELS = {"note": "note", "hit": "drum hit"}


def _snap(root, sec, grid, strength, swing=0.0):
    b = tempo.beat_at(root, sec)
    return tempo.seconds_at(root, b + (meter.snap(root, b, grid, swing) - b) * strength)


def _quantize(kind):
    @REGISTRY.operation(f"{kind}.quantize", f"Snap the selected {LABELS[kind]}s to a grid (in beats), all the way "
                        "or part of the way; with `swing` (0 … 1) the off-beat lines sit late (1 = triplet) and the swing is written "
                        "into the times." + (" Optionally the ends too." if kind == "note" else ""),
                        target=kind, params=[GRID, STRENGTH, SWING, *([ENDS] if kind == "note" else [])],
                        label=f"Quantize {LABELS[kind]}s")
    def quantize(ctx, targets, args):
        root, grid, strength, swing = ctx.doc, args.get("grid", 0.25), args.get("strength", 1), args.get("swing", 0)
        plan = []
        for t in targets:
            item = ctx.item(t)
            start = start_of(root, item)
            new = _snap(root, start, grid, strength, swing)
            plan.append((t, "at", at_seconds(ctx, item, new)))
            if args.get("ends") and kind == "note":
                end = _snap(root, end_of(root, item), grid, strength, swing)
                if end <= new + 1e-6:
                    end = tempo.seconds_at(root, tempo.beat_at(root, new) + grid)
                length = note_dur(root, item, new, end)
                if length is not None:
                    plan.append((t, "dur", length))
        for t, k, v in plan:
            ctx.set(t, k, v)


def _humanize(kind):
    @REGISTRY.operation(f"{kind}.humanize", f"Make the selected {LABELS[kind]}s a little looser: tiny changes to "
                        "when they start (± `timing` ms, default 10), how hard they play (± `velocity`, default 0.05)"
                        + (" and how long they last (± `length` share, default 0)" if kind == "note" else "")
                        + ". Written into the notes. The same seed gives the same result; another seed, another take.",
                        target=kind, params=[TIMING, VELOCITY, *([LENGTH] if kind == "note" else []), SEED],
                        label=f"Humanize {LABELS[kind]}s")
    def humanize(ctx, targets, args):
        root, ms, vel, share = ctx.doc, args.get("timing", 10), args.get("velocity", 0.05), args.get("length", 0)
        for t in targets:
            item, rnd = ctx.item(t), random.Random(f'{args.get("seed", 1)}:{t}')
            dt, dv = rnd.uniform(-ms, ms) / 1000, rnd.uniform(-vel, vel)
            start = start_of(root, item)
            if share:                                   # drawn after timing and velocity: their old results stay
                k, end = 1 + rnd.uniform(-share, share), end_of(root, item)
                dur = note_dur(root, item, start + dt, start + dt + (end - start) * k) if end > start else None
                if dur is not None:
                    ctx.set(t, "dur", dur)
            if ms:
                ctx.set(t, "at", at_seconds(ctx, item, start + dt))
            if vel:
                ctx.set(t, "vel", round(min(1.0, max(0.0, item.get("vel", 0.8) + dv)), 4))


for _kind in LABELS:
    _quantize(_kind)
    _humanize(_kind)
