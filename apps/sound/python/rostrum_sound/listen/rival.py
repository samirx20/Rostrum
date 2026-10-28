"""rival: an attack in the second before an asked hit or climax that is as strong as the moment's own.

Round deliver-clean, Ascent r2: a timpani pickup at 37.07 s struck 1.9x harder than the 38.0 s climax. One judge heard
the climax land 0.93 s early and capped the piece; the check passed it (the climax's own attack was strong enough).
A listener takes the strongest attack near a moment as the moment, so a stronger one just before it moves the moment.
Measured on the same onset curve as the hit (attack.curves); a stop has its own rule (moments.blurred_stop)."""
from __future__ import annotations

from . import attack
from .core import num

BEFORE_S = 1.0          # the window before the moment a listener still hears as "the moment arriving"
SHARE = 1.0             # an attack there at least as strong as the moment's own takes the moment (bench: 1.9x faulted, ≤ 0.74x fine)


def faults(wav, at: float, kind: str, strike: dict) -> list[dict]:
    """[{"kind": "early_rival", ...}] when an onset in [at - BEFORE_S, at - attack.NEAR_S) is ≥ SHARE x the moment's
    attack (`strike`: attack.strike at `at`)."""
    c = attack.curves(wav)
    env, t, pk = c["env"], c["t"], c["pk"]
    own = strike["times_typical"] * c["typ"]
    before = [p for p in pk if at - BEFORE_S <= t[p] < at - attack.NEAR_S]
    if not before or own <= 0:
        return []
    p = max(before, key=lambda q: env[q])
    share = float(env[p] / own)
    if share < SHARE:
        return []
    return [{"kind": "early_rival", "at_s": at, "measured": {"moment": kind, "rival_s": num(float(t[p]), 2),
             "early_s": num(at - float(t[p]), 2), "rival_x": num(share, 2)}}]


def words(f) -> str:
    d, t = f["measured"], f["at_s"]
    return (f"{d['moment']} at {t:.2f} s arrives early to the ear: an attack at {d['rival_s']:g} s, {d['early_s']:g} s "
            f"before it, strikes {d['rival_x']:g}x as hard as the {d['moment']} itself, so a listener takes it as the "
            f"moment; make the {d['moment']} the strongest attack: soften or shorten that earlier note (a pickup, a "
            f"timpani or drum stroke: lower vel, or move it onto {t:g}), or rest it in a script "
            f"(m = moment(\"{d['moment']}\", at={t:g}); m.rest(<that track>, before={d['early_s'] + 0.1:.1f})); "
            "look_music events with by_stem names the track")
