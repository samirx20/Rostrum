"""weakest: the three weakest moments of a finished render against the asked moments, one short line each.

A render reply that only says "listen and fix" lets an agent stop after a fifth of its time (sound-gaps round 1: ~4 of
15 minutes). This puts the evidence in the reply: each line the time, what is weak, the measured number and the first
fix, so the fix pass is the obvious next step. Moments come from `expect` or from the song's markers named for one
(a marker "hit", "Big hit", "stop", "drums out", "drums back", "climax", "lift")."""
from __future__ import annotations

from .faults import check as fault_check, heard, weak_fixes
from .moments import strengths

NAMES = (("back", "entry"), ("return", "entry"), ("entry", "entry"), ("hit", "hit"), ("stop", "stop"), ("out", "drop"),
         ("drop", "drop"), ("climax", "climax"), ("peak", "climax"), ("lift", "lift"))   # first word found wins
LINES = 3


def kind_of(name: str) -> str | None:
    """The moment a marker's name asks for ("Drums back" -> entry), None for a marker that names none."""
    words = name.lower().replace("-", " ").replace("_", " ").split()
    return next((k for w, k in NAMES if w in words), None)


def from_markers(marks) -> list[dict]:
    """[(name, seconds)] -> the asked moments among them."""
    return [{"at": t, "kind": k} for n, t in marks if (k := kind_of(n))]


def _order(f) -> float:
    """Missing first, then weak by how far under (times a normal note), then the other moment faults, then the whole piece's."""
    k, d = f["kind"], f["measured"]
    if k.startswith("no_"):
        return -1.0
    if k.startswith("weak_"):
        return d["times_typical"]
    return 50.0 if k in ("held_tone", "near_mono") else 10.0


def _line(f) -> str:
    k, t, d = f["kind"], f["at_s"], f["measured"]
    if k.startswith("weak_"):
        return f"{t:.2f} s weak {k[5:]}: {heard(d)}. Fix: {weak_fixes(t, d)[0]}."
    return f"{f['words'][:1].upper()}{f['words'][1:]}."


def lines(wav, moments) -> list[str]:
    """Up to three lines, the weakest first: the faults found (asked moments before the whole piece's), then, when there
    are fewer, the asked hits that pass with their numbers (the margin left)."""
    found = sorted(fault_check(wav, moments)["faults"], key=_order)
    out = [_line(f) for f in found[:LINES]]
    if len(out) < LINES and moments:
        faulted = {round(f["at_s"], 2) for f in found}
        ok = [s for s in strengths(wav, moments) if s["strike"] and round(s["at"], 2) not in faulted]
        for s in sorted(ok, key=lambda s: s["strike"]["times_typical"])[:LINES - len(out)]:
            d = s["strike"]
            out.append(f"{s['at']:.2f} s {s['kind']} comes across: {d['times_typical']:.1f}x a normal note (rank {d['rank']}), "
                       f"bright attack {d['bright_x']:.1f}x.")
    return out


def words(wav, moments) -> str:
    """The render reply's lines: a head, then the weakest moments numbered, one per line."""
    if moments:
        head, found = f"Weakest moments ({len(moments)} asked):", lines(wav, moments)
    else:
        head = ("No asked moments to check: pass `expect` ([{\"at\": 31.5, \"kind\": \"hit\"}]) or name markers hit / stop / "
                "drums out / drums back / climax / lift.")
        found = lines(wav, [])
    return head + "".join(f"\n{i}. {s}" for i, s in enumerate(found, 1))
