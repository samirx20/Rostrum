"""Chord rhythm (comping) and the arpeggiator: a progression played across its bars, as a line of plain notes.

comp: each chord voiced (voicing.py) and struck in a rhythm:
    "hold" one strike per chord (the default) | "whole" | "half" | "quarter" | "8ths" | "16ths" | "offbeat"
    "x..x..x.x-x-...."  16ths per bar: x / X (accent) strike, - holds, . rests       [0, 1.5, 2.5]  beats in the bar
`push` (beats) brings every change that much early: the anticipation that leans a progression forward.

arp: the chord's notes (or the notes given) one at a time: modes up, down, upDown, downUp, converge, diverge, order,
random (seeded: the same every run), chord (all together on each step); `rate` in beats or a 16ths `pattern`.
"""
from __future__ import annotations

import hashlib

from .line import grid
from .pitch import midi, name, refuse
from .voicing import voice

GRIDS = {"whole": (0, None), "half": (0, 2), "quarter": (0, 1), "8ths": (0, 0.5), "16ths": (0, 0.25), "offbeat": (0.5, 1)}
RHYTHMS = ['"hold"', *(f'"{g}"' for g in GRIDS), '"x..x..x.x-x-...." (16ths: x / X strike, - holds, . rests)', "[0, 1.5, 2.5] (beats in the bar)"]
ARP_MODES = ("up", "down", "upDown", "downUp", "converge", "diverge", "order", "random", "chord")


def _bar_strikes(rhythm, beats_per_bar: float, where: str) -> list[tuple[float, float | None, float]]:
    """(at, held length or None = to the next strike, velocity) in one bar."""
    if isinstance(rhythm, (list, tuple)):
        if not rhythm or any(not isinstance(b, (int, float)) or not 0 <= b < beats_per_bar for b in rhythm):
            refuse(where, f"rhythm {rhythm!r}", f"as a list is beats in the bar, 0 … under {beats_per_bar:g}", RHYTHMS)
        return [(float(b), None, 0.8 if b % 1 == 0 else 0.7) for b in sorted(rhythm)]
    if rhythm in GRIDS:
        first, step = GRIDS[rhythm]
        step = step or beats_per_bar
        n = int(round((beats_per_bar - first) / step + 0.4999))
        return [(first + i * step, None, 0.8 if (first + i * step) % 1 == 0 else 0.68) for i in range(n)]
    if isinstance(rhythm, str) and rhythm.strip("xX-. |"):
        refuse(where, f"rhythm {rhythm!r}", "is not a rhythm", RHYTHMS)
    if isinstance(rhythm, str):
        return [(a, ln, 0.88 if c == "X" else 0.72) for a, ln, c in grid(rhythm, int(beats_per_bar * 4), "xX", where)]
    refuse(where, f"rhythm {rhythm!r}", "is not a rhythm", RHYTHMS)


def comp(chords, key=None, rhythm="hold", per=4, push=0.0, vel=0.7, beats_per_bar=4, where="comp", **voicing) -> list[dict]:
    """The progression as chords in a rhythm: each chord lasts `per` beats (a bar of 4/4 by default)."""
    voiced = voice(chords, key, where=where, **voicing)
    total = per * len(voiced)
    if not 0 <= push < per:
        refuse(where, f"push={push!r}", f"is beats each change comes early, 0 … under one chord's {per:g} beats", ["0.5 (an eighth early)"])
    starts = [0.0] + [i * per - push for i in range(1, len(voiced))]
    ends = starts[1:] + [float(total)]
    if rhythm == "hold":
        return [{"pitch": v, "at": s, "dur": e - s, "vel": vel} for v, s, e in zip(voiced, starts, ends)]
    strikes = _bar_strikes(rhythm, beats_per_bar, where)
    times = [(b * beats_per_bar + a, ln, v) for b in range(int(-(-total // beats_per_bar))) for a, ln, v in strikes
             if b * beats_per_bar + a < total - 1e-9]
    out = []
    for i, (t, ln, v) in enumerate(times):
        idx = min(len(voiced) - 1, int((t + push) / per + 1e-9))
        nxt = times[i + 1][0] if i + 1 < len(times) else total
        end = min(t + ln if ln is not None else nxt, ends[idx], total)
        out.append({"pitch": voiced[idx], "at": t, "dur": end - t if ln is not None or end < nxt else (end - t) * 0.95,
                    "vel": round(vel * v / 0.8, 3)})
    return out


def _order(tones: list[int], mode: str, seed: str) -> list[list[int]]:
    up = sorted(tones)
    down = up[::-1]
    inward = [up[i // 2] if i % 2 == 0 else up[-1 - i // 2] for i in range(len(up))]
    seq = {"order": tones, "up": up, "down": down, "upDown": up + down[1:-1], "downUp": down + up[1:-1],
           "converge": inward, "diverge": inward[::-1],
           "random": sorted(up, key=lambda m: hashlib.sha1(f"{seed}:{m}".encode()).hexdigest())}
    return [up] if mode == "chord" else [[m] for m in seq[mode] or up]


def arp(source, key=None, mode="up", rate=0.5, pattern=None, octaves=1, gate=0.9, per=4, vel=0.7, beats_per_bar=4,
        bars=None, where="arp", **voicing) -> list[dict]:
    """Chords (each for `per` beats, voiced in range A3–E5 unless given) or notes (repeating for `bars`) one at a time."""
    if isinstance(source, str):
        source = [source]
    if mode not in ARP_MODES:
        refuse(where, f"mode {mode!r}", "is not an arpeggio mode", [repr(m) for m in ARP_MODES])
    if not (isinstance(octaves, int) and 1 <= octaves <= 4) or not 0 < gate <= 2:
        refuse(where, f"octaves={octaves!r}, gate={gate!r}", "are 1 … 4 octaves and a gate 0 … 2 of each step")
    as_notes = all(_is_note(p) for p in source)
    if as_notes:
        sets = [[midi(p, where) for p in source]]
        total = (bars or 1) * beats_per_bar
        per = total
    else:
        sets = [[midi(n, where) for n in v] for v in voice(source, key, where=where, **{"range": ("A3", "E5"), **voicing})]
        total = per * len(sets)
    sets = [stack(s, octaves) for s in sets]
    if pattern is not None:
        steps = [(a, ln, 0.88 if c == "X" else 0.72) for a, ln, c in grid(pattern, int(round(total * 4)), "xX", where)]
    else:
        if not (isinstance(rate, (int, float)) and rate > 0):
            refuse(where, f"rate={rate!r}", "is the step in beats", ["0.5 (8ths)", "0.25 (16ths)", "1/3 (8th triplets)"])
        steps = even_steps(total, rate)
    played = play(steps, sets, per, mode, lambda idx: f"{where}:{idx}", min(gate / 0.9, 1.2) if pattern is not None else gate)
    return [{"pitch": name(tones[0], key) if len(tones) == 1 else [name(m, key) for m in tones], "at": at,
             "dur": dur, "vel": round(vel * v / 0.8, 3)} for at, dur, tones, v in played]


def stack(tones: list[int], octaves: int) -> list[int]:
    """The tones, then the same an octave up, … for `octaves` octaves."""
    return [m + 12 * o for o in range(octaves) for m in tones]


def even_steps(total: float, rate: float) -> list[tuple[float, float, float]]:
    """(at, length, accent) every `rate` beats over `total` beats; every 4th step leads."""
    return [(i * rate, rate, 0.84 if i % 4 == 0 else 0.7) for i in range(int(total / rate + 1e-6))]


def play(steps, sets, per, mode, seed, gate) -> list[tuple[float, float, list[int], float]]:
    """The arpeggio: (at, length, tones, accent) for each step, stepping through the tone set playing then (a set lasts
    `per` beats) in `mode`'s order, each step held `gate` of its length. `seed(set index)` seeds "random". The one
    arpeggio rule for the script's arp(...) and the document's note.arpeggiate."""
    out, current, k, seq = [], -1, 0, []
    for at, ln, v in steps:
        idx = min(len(sets) - 1, int(at / per + 1e-9))
        if idx != current:
            current, k, seq = idx, 0, _order(sets[idx], mode, seed(idx))
        tones = seq[k % len(seq)]
        k += 1
        out.append((at, ln * gate, tones, v))
    return out


def _is_note(p) -> bool:
    try:
        midi(p, "")
        return True
    except Exception:
        return False
