"""passing: what a passing version of an asked moment measures, and how near this one is.

Round 3E: `keep` on the brief's own moment was the easy way out (three judge faults were moments the agent had kept: a
hit 0.9x a normal note, a stop +0.18 LU, drums back weakly). So each moment fault names the numbers that pass and a
stated distance from them ("near"): only a moment that measures inside that distance may be kept. A fault with no
measured number (nothing starts there) is never near. The pass values are the checks' own (moments.py, rival.py,
drop_gap.py, faults.py), read from there, never copied.

    gaps(raw_fault) -> [{"what", "now", "passes", "near", "ok": now passes, "close": within near}]
    near(raw_fault) -> True when every failing number is within its stated distance
    words(raw_fault) -> "passes at: attack 2.5x a normal note or more (now 1.9x; keepable from 2.2x)"
"""
from __future__ import annotations

from . import drop_gap, moments as mo, rival
from .faults import SQUASH_DB
from .speech_room import TARGET_DB

# (measured key, at least / at most, pass, near, words, unit); near = the stated distance a kept moment must be within
_ATTACK = ("times_typical", ">=", mo.WEAK_X, 2.2, "attack", "x a normal note")
_RANK = ("rank", "<=", mo.WEAK_RANK, mo.WEAK_RANK + 1, "rank among the file's onsets", "")
_BEFORE = ("beat_before_share", "<=", mo.BLUR_SHARE, 0.8, "the beat before it", "x as strong")
_FALL = ("fall_after_db", ">=", mo.STOP_DROP_DB, 6.5, "fall in the second after it", " dB")

RULES = {
    "weak_hit": [_ATTACK, _RANK], "weak_climax": [_ATTACK, _RANK], "weak_stop": [_ATTACK, _RANK],
    "weak_entry": [("times_typical", ">=", mo.WEAK_ENTRY_X, 1.8, "attack", "x a normal note")],
    "soft_stop": [_ATTACK, _RANK, _BEFORE, _FALL], "blurred_stop": [_BEFORE, _FALL],
    "flat_lift": [("rise_lu", ">=", mo.LIFT_LU, 1.5, "the 3 s after over the 3 s before", " LU")],
    "flat_top": [("grew_db", ">=", mo.GROW_DB, 4.5, "top end brighter than the start", " dB")],
    "squashed_hit": [("reduced_db", "<=", SQUASH_DB, 4.0, "limiting on it", " dB")],
    "short_climax": [("held_s", ">=", mo.HOLD_S, 2, "held over the build", " s")],
    "late_climax": [("off_s", "<=", mo.CLIMAX_LATE_S, 3.5, "loudest moment after the downbeat", " s")],
    "early_climax": [("off_s", ">=", -mo.CLIMAX_EARLY_S, -0.75, "loudest moment against the downbeat", " s")],
    "early_rival": [("rival_x", "<=", rival.SHARE, 1.15, "the attack before it", "x the moment's")],
    "build_at_ceiling": [("headroom_db", ">=", mo.CEILING_NEAR_DB, 1.0, "build under the file's loudest peak", " dB")],
    "busy_speech_band": [("room_db", ">=", TARGET_DB, TARGET_DB - 1.5, "voice over the music in 1–4 kHz", " dB")],
}

def _rules(f) -> list[tuple]:
    d, k = f.get("measured") or {}, f["kind"]
    if k == "early_drop":                     # the last beat may sit up to 1.5 beat gaps (0.35 s at least) before the drop
        ok = max(mo.DROP_MIN_S, mo.DROP_LATE_X * float(d.get("beat_gap_s") or 0.5))
        return [("early_s", "<=", round(ok, 2), round(ok + 0.15, 2), "last beat before the drop", " s")]
    if k == "drums_in_gap":
        need = drop_gap.STEM_GAP_DB if d.get("on") == "tracks" else drop_gap.GAP_DB
        return [("down_db", ">=", need, need - 3, "drums in the gap under the 2 s before", " dB")]
    rules = RULES.get(k, [])
    if k == "soft_stop" and not d.get("weak"):
        rules = [_BEFORE, _FALL]              # its attack was strong enough: only the blur numbers count
    return [r for r in rules if d.get(r[0]) is not None]


def _fits(now, op, bound) -> bool:
    return now >= bound if op == ">=" else now <= bound


def gaps(f) -> list[dict]:
    d = f.get("measured") or {}
    return [{"what": what, "now": float(d[key]), "passes": bound, "near": near, "op": op, "unit": unit,
             "ok": _fits(float(d[key]), op, bound), "close": _fits(float(d[key]), op, near)}
            for key, op, bound, near, what, unit in _rules(f)]


def near(f) -> bool:
    """Every failing number within its stated distance. A fault none of whose numbers fail is failing on something
    unmeasured here: never near (round sound-tighten: a stop ranked 53rd was kept while only its attack was read)."""
    g = gaps(f)
    return any(not x["ok"] for x in g) and all(x["ok"] or x["close"] for x in g)


def _short(unit) -> str:
    return "x" if unit.startswith("x") else unit          # "x a normal note" is said once, on the pass value


def _n(v, unit) -> str:
    return f"{v:g}{unit}"


def words(f) -> str:
    """What a passing version of this moment measures, with this one's number and the keepable bound."""
    g = [x for x in gaps(f) if not x["ok"]]
    if not g:
        need = "a sound starting on the time" if f["kind"].startswith("no_") else "its fix"
        return f"passes with {need} (no number to be near, so it cannot be kept: fix it, or move the moment itself in the script)"
    side = {">=": "or more", "<=": "or less"}
    return "passes at: " + "; ".join(f"{x['what']} {_n(x['passes'], x['unit'])} {side[x['op']]} (now {_n(round(x['now'], 2), _short(x['unit']))}; "
                                     f"keepable from {_n(x['near'], _short(x['unit']))})" for x in g)
