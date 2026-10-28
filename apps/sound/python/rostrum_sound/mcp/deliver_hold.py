"""Delivery waits for a clean check: render_mix's `folder` copy (the delivery) is held while the listening check has
open faults, unless the call keeps each one on purpose (`keep`: the fault, and why).

Three benchmark rounds: agents read the check's faults ("weak hit 0.7x", "-17.4 LUFS", "drums 5.6 dB down") and
delivered anyway, using ~3 of their 15 minutes. So the render still happens (its version stands in renders/ and the
reply has the whole check), but nothing is copied to `folder` while a fault is open and unexplained; the reply says
what is open, what to change, and the exact `keep` that would deliver it as it is. Besides the listening faults
(listen/faults.py) the delivery's own: a file longer than the song's length plus the ring allowed, loudness off the
master's target by more than LOUD_LU, a true peak over the master's ceiling, clipped samples."""
from __future__ import annotations

import json

from rostrum_core import RostrumError, codes

from ..listen.faults import check as fault_check

LOUD_LU = 1.0          # a delivery within 1 LU of its loudness target (the usual delivery spec)
PEAK_SLACK_DB = 0.05   # the true-peak reading's own rounding
LONG_SLACK_S = 0.05
NEAR_S = 0.5           # a kept fault with a time matches an open one this close
WHY_MIN = 12           # characters: "on purpose" is not a reason; "the drone is the scene's tension" is

KEEP = {"keep": {"type": "array", "items": {"type": "object", "properties": {
            "fault": {"type": "string", "description": "The fault's kind as the reply names it (weak_hit, held_tone, off_loudness …)."},
            "at": {"type": "number", "description": "Its time in seconds (optional: without it every fault of that kind is kept)."},
            "why": {"type": "string", "description": "Why it stays, in a sentence (\"the drone is the scene's held breath\")."}},
            "required": ["fault", "why"]},
        "description": "Faults the delivery keeps on purpose. With `folder`, the mix is copied there only when the listening check "
                       "is clean or every open fault is in `keep` with its reason; otherwise the render stands in renders/ and the "
                       "reply lists what is open, what to change, and the `keep` that would deliver it as it is."}}


def delivery_faults(r: dict, master: dict, length_s: float | None, ring_s: float) -> list[dict]:
    """The file's own faults against what the song asks: length, loudness target, ceiling, clipping."""
    out = []
    if length_s is not None and r["seconds"] > length_s + ring_s + LONG_SLACK_S:
        out.append({"kind": "runs_long", "at_s": round(length_s, 2), "measured": {"seconds": round(r["seconds"], 2)},
                    "words": f"the file is {r['seconds']:.2f} s, {r['seconds'] - length_s:.2f} s past the song's length "
                             f"({length_s:.2f} s; {ring_s:g} s of ring allowed): end the last notes earlier or render without "
                             "ring_past_length (the ring is then faded inside the length)"})
    if master.get("normalize"):
        goal = master.get("loudness", -16)
        off = r["lufs"] - goal
        if abs(off) > LOUD_LU:
            side = "under" if off < 0 else "over"
            out.append({"kind": "off_loudness", "at_s": 0.0, "measured": {"lufs": round(r["lufs"], 2), "target": goal},
                        "words": f"loudness {r['lufs']:.1f} LUFS, {abs(off):.1f} LU {side} the {goal:g} target (±{LOUD_LU:g} allowed)"})
    ceiling = master.get("truePeak", -1)
    if r.get("truePeak") is not None and r["truePeak"] > ceiling + PEAK_SLACK_DB:
        out.append({"kind": "peak_over", "at_s": 0.0, "measured": {"true_peak": round(r["truePeak"], 2), "ceiling": ceiling},
                    "words": f"true peak {r['truePeak']:.1f} dBTP over the {ceiling:g} ceiling"})
    if r.get("clipped"):
        out.append({"kind": "clipped", "at_s": 0.0, "measured": {"samples": r["clipped"]},
                    "words": f"{r['clipped']} clipped samples in the mix"})
    return out


def open_faults(r: dict, moments, master: dict, length_s, ring_s, loud_fix: str = "", limiter=None, peaky=None) -> list[dict]:
    """Every fault a delivery would ship: the listening check's (asked moments and the whole piece) and the file's."""
    try:
        heard = fault_check(r["file"], moments, limiter, peaky=peaky)["faults"]
    except RostrumError as e:          # a file the ears cannot read is not delivered as if it were clean
        heard = [{"kind": "unreadable", "at_s": 0.0, "measured": {}, "words": f"the listening check could not read the mix: {e}"}]
    own = delivery_faults(r, master, length_s, ring_s)
    for f in own:
        if f["kind"] == "off_loudness" and loud_fix:
            f["words"] += f"; {loud_fix}"
    return sorted(heard + own, key=lambda f: f["at_s"])


def read_keep(keep) -> list[dict]:
    """`keep` checked before anything renders: each entry a fault kind and a real reason."""
    out = []
    for i, k in enumerate(keep or []):
        w = f"render_mix › keep[{i}]"
        if not isinstance(k, dict) or not isinstance(k.get("fault"), str) or not k["fault"].strip():
            raise RostrumError(codes.BAD_ARGUMENT, w, repr(k), "is not a kept fault", hint='{"fault": "held_tone", "at": 0, "why": "the drone is the scene\'s held breath"}')
        why = str(k.get("why") or "").strip()
        if len(why) < WHY_MIN:
            raise RostrumError(codes.BAD_ARGUMENT, w, f'why "{why}"', "does not say why the fault stays",
                               hint="One sentence on why it is right for this piece; or fix the fault and render again.")
        at = k.get("at")
        if at is not None and (isinstance(at, bool) or not isinstance(at, (int, float))):
            raise RostrumError(codes.BAD_ARGUMENT, w, f"at={at!r}", "is not a time in seconds", hint="The fault's time as the reply gives it, e.g. 31.5.")
        out.append({"fault": k["fault"].strip(), "at": at, "why": why})
    return out


def _kept(f, keep) -> dict | None:
    return next((k for k in keep if k["fault"] == f["kind"] and (k["at"] is None or abs(k["at"] - f["at_s"]) <= NEAR_S)), None)


def decide(faults: list[dict], keep: list[dict]) -> tuple[list[dict], list[dict]]:
    """-> (open: the faults no `keep` explains, kept: [{fault, at, why}] that matched)."""
    still, kept = [], []
    for f in faults:
        k = _kept(f, keep)
        (kept.append({"fault": f["kind"], "at": f["at_s"], "why": k["why"]}) if k else still.append(f))
    return still, kept


def held_words(still: list[dict], folder: str) -> str:
    """The reply's lead when the delivery is held: what is open, what to change, the `keep` that delivers it as is."""
    lines = "".join(f"\n- {f['kind']} at {f['at_s']:g} s: {f['words']}" for f in still)
    keep = json.dumps([{"fault": f["kind"], "at": f["at_s"], "why": "…"} for f in still], ensure_ascii=False)
    return (f"NOT DELIVERED: nothing was copied to {folder}, because the listening check has {len(still)} open "
            f"fault{'s' * (len(still) != 1)}:{lines}\nChange what each line says and render again to the same folder and name. "
            f"A fault that is right for this piece is delivered by explaining it in the same call: \"keep\": {keep} "
            "(each why one sentence on why it stays).")


def clean_words(faults: list[dict], kept: list[dict]) -> str:
    if kept:
        return f"Delivered with {len(kept)} fault{'s' * (len(kept) != 1)} kept on purpose: " + "; ".join(f"{k['fault']} at {k['at']:g} s ({k['why']})" for k in kept) + "."
    return "Delivered: the listening check is clean."


def pending_words(faults: list[dict]) -> str:
    """A render without `folder` is a check, not a delivery: say what a delivery would wait for."""
    if not faults:
        return "The check is clean: a render with `folder` delivers it."
    return (f"Open faults: {len(faults)} ({', '.join(sorted({f['kind'] for f in faults}))}). A delivery (`folder`) waits until each "
            "is fixed or kept on purpose with `keep`.")
