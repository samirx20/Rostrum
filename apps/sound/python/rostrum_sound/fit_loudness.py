"""fit_loudness: what to change so the mix reaches the master's loudness target within the master's `maxLimit`.

With the loudness target on, the engine turns the whole mix to the target, so no common track gain can move the
loudness: only what stands above the average (the peaks) decides how much limiting the target needs. Gentle limiting
(`maxLimit`) holds the mix down instead of limiting more, which is why a first render lands under the target.
Two ways out, both exact because the engine measures them, never guessed:
  keep the balance -> `maxLimit` = the limiting the target needs (the last render says it: pulled + held);
  keep the limit   -> lower one track (the most peaked, or the one asked) by the smallest amount that lands the render
                      on the target within `maxLimit` (a short search of offline renders of the compiled song)."""
from __future__ import annotations

import copy
import math
from pathlib import Path

from .compile import compile as compile_doc
from .doc.fields import FIELDS

SHORT_OK = 0.3                 # a render within this many dB under the target has reached it (the engine itself settles within 0.2)
STEP_DB = 0.1                  # the search stops at this fineness
MAX_LIMIT = next(f.max for f in FIELDS["master"] if f.name == "maxLimit")
MAX_TRIM_DB = 12.0       # past this the track is all but gone: not an answer


def need_db(r: dict) -> float:
    """The limiting the target needs, in dB: what the limiter pulled in this render plus what was held down."""
    m = r.get("master") or {}
    return round((m.get("limiterMaxReductionDb") or 0) + (m.get("heldDb") or 0), 2)


def peakiest_track(r: dict) -> str | None:
    """The track whose peaks stand highest over its own average (peak / rms): the one a limiter works on."""
    t = max(r.get("tracks") or [], key=lambda t: (t.get("peak") or 0) / max(t.get("rms") or 0, 1e-9), default=None)
    return t["id"] if t else None


def trimmed_volume(track: dict, db: float) -> float:
    return round(track.get("volume", 0.85) * 10 ** (-db / 20), 4)


def trimmed(root: dict, track: str, db: float) -> dict:
    """A copy of the document data with `track`'s volume lowered by `db` (the document itself is never touched)."""
    data = copy.deepcopy(root)
    t = next(t for t in data["tracks"] if t["id"] == track)
    t["volume"] = trimmed_volume(t, db)
    return data


def solve(measure, short0: float, cap: float = MAX_TRIM_DB, step: float = STEP_DB):
    """The smallest trim (dB, to `step`) after which `measure(db)` -> how far under the target the render lands (dB) is
    under SHORT_OK; None when `cap` is not enough. The shortfall only falls as the trim grows: first try the shortfall
    itself, double until it is met, then halve."""
    lo, hi = 0.0, max(step, short0)
    while measure(hi) >= SHORT_OK:
        if hi >= cap:
            return None
        lo, hi = hi, min(hi * 2, cap)
    while hi - lo > step:
        mid = (lo + hi) / 2
        lo, hi = (lo, mid) if measure(mid) < SHORT_OK else (mid, hi)
    return round(math.ceil(hi / step - 1e-9) * step, 2)


def _keep_balance(goal, need, limit):
    ask = math.ceil((need + 0.05) * 10) / 10
    if ask > MAX_LIMIT:
        return {"name": "keep_balance", "impossible": True,
                "words": f"Reaching {goal:g} LUFS as written needs {need:g} dB of limiting, more than the master's top {MAX_LIMIT:g} dB: not possible without changing the balance."}
    return {"name": "keep_balance", "max_limit_db": ask, "ops": [{"op": "master.set", "target": ["master"], "args": {"maxLimit": ask}}],
            "words": f"Reach {goal:g} LUFS with the balance exactly as written: the limiter then pulls up to {ask:g} dB (now allowed: {limit:g})."}


def _trim(goal, limit, short, who, tracks, root, engine, scratch):
    renders = [0]

    def measure(db):
        renders[0] += 1
        got = engine.request("render", schedule=compile_doc(trimmed(root, who, db)), out=str(scratch / "fit.wav"), stems=[])
        return goal - got["lufs"]

    db = solve(measure, short)
    if db is None:
        return {"name": "trim_track", "track": who, "impossible": True,
                "words": f"Lowering {who} by up to {MAX_TRIM_DB:g} dB does not reach the target within {limit:g} dB: the peaks come from more than {who} (pass `track` to try another)."}
    was = tracks[who].get("volume", 0.85)
    vol = trimmed_volume(tracks[who], db)
    return {"name": "trim_track", "track": who, "trim_db": db, "volume": vol, "was": was, "renders": renders[0],
            "ops": [{"op": "track.set", "target": [who], "args": {"volume": vol}}],
            "words": f"Reach {goal:g} LUFS inside the {limit:g} dB limit by lowering {who} by {db:.1f} dB (volume {was:g} -> {vol:g}); the balance moves: "
                     f"{who} sits {db:.1f} dB lower against the rest."}


def plan(r: dict, master: dict, tracks: dict, root: dict, engine, scratch: Path, track: str | None = None) -> dict:
    """The options for the last render `r`. `master`: the document's master fields; `tracks`: {id: track}."""
    goal = master.get("loudness") if master.get("normalize") else None
    limit = master.get("maxLimit", 2) if master.get("gentle") else None
    out = {"target": goal, "lufs": r["lufs"], "need_db": need_db(r), "max_limit": limit}
    if goal is None:
        return {**out, "state": "no target", "words": "The master has no loudness target (normalize is off): the level is what the faders add up to.",
                "options": [{"name": "set_target", "words": "Turn the loudness target on.",
                             "ops": [{"op": "master.set", "target": ["master"], "args": {"normalize": True, "loudness": master.get("loudness", -16)}}]}]}
    short = goal - r["lufs"]
    if limit is None or short < SHORT_OK:
        return {**out, "state": "on target", "words": f"The render is on the {goal:g} LUFS target ({r['lufs']:.1f}); nothing to fit.", "options": []}
    options = [_keep_balance(goal, out["need_db"], limit)]
    who = track or peakiest_track(r)
    if who in tracks:
        options.append(_trim(goal, limit, short, who, tracks, root, engine, scratch))
    return {**out, "state": "under target", "short_db": round(short, 2), "options": options,
            "words": f"The render landed {short:.1f} dB under the {goal:g} LUFS target: the limiter's need is {out['need_db']:g} dB and the master allows {limit:g}."}
