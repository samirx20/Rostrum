"""asked_starts: render_mix's `expect` entries given as a bare time (seconds, {"beat": n}, "#marker").

`expect`'s description says a bare time asks that a sound start there. render_mix kept only the entries with a kind,
so `expect: ["#features", "#hero"]` was dropped whole and the reply said "No asked moments to check: pass `expect`"
(sound production 2026-10-30, a6). Now a bare "#marker" whose name asks for a moment (hit, stop, drums back ...:
weakest.kind_of) is that moment, as an unasked marker of that name already is; every other bare time is a start
check: the mix's nearest onset to it, early or late, within one frame at 25 fps."""
from __future__ import annotations

from .onsets import onsets
from .weakest import kind_of

TOLERANCE_S = 0.04


def split(times, labels) -> tuple[list[dict], list[tuple[str, float]]]:
    """(moments named by their marker, [(label, seconds)] to check for a start) of `expect`'s bare times."""
    moments, starts = [], []
    for t, label in zip(times, labels):
        kind = kind_of(label[1:]) if isinstance(label, str) and label.startswith("#") else None
        if kind:
            moments.append({"at": t, "kind": kind})
        else:
            starts.append((str(label), t))
    return moments, starts


def check(wav, starts) -> tuple[str, list[dict]]:
    """One reply line and the rows ({at, expected_s, nearest_onset_s, offset_ms, pass}) for the asked starts."""
    if not starts:
        return "", []
    r = onsets(wav, expect=[t for _, t in starts], tolerance=TOLERANCE_S)
    rows = [{"at": label, **row} for (label, _), row in zip(starts, r["expected"])]
    ok = sum(row["pass"] for row in rows)
    off = [f"{row['at']} ({row['expected_s']:.2f} s): " + ("nothing starts within 250 ms" if row["offset_ms"] is None
           else f"nearest start {row['offset_ms']:+.0f} ms") for row in rows if not row["pass"]]
    return (f"Asked starts: {ok} of {len(rows)} have a sound starting within {TOLERANCE_S * 1000:.0f} ms"
            + (": off " + "; ".join(off) if off else "") + "."), rows
