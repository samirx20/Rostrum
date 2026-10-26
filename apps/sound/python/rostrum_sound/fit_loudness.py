"""fit_loudness: what to change so the mix reaches the master's loudness target within the master's `maxLimit`.

With the loudness target on, the engine turns the whole mix to the target, so no common track gain can move the
loudness: only what stands above the average (the peaks) decides how much limiting the target needs. Gentle limiting
(`maxLimit`) holds the mix down instead of limiting more, which is why a first render lands under the target.
Three ways out, all exact because the engine measures them, never guessed:
  keep the balance -> `maxLimit` = the limiting the target needs (the last render says it: pulled + held);
  keep the limit   -> lower one track (the most peaked, or the one asked) by the smallest amount that lands the render
                      on the target within `maxLimit` (a short search of offline renders of the compiled song);
  tame the peaks   -> a gentle compressor on the most peaked track(s), threshold searched, makeup measured so the track keeps
                      its place against the mix: the target within `maxLimit`, the balance as written (fit_peaks.py)."""
from __future__ import annotations

import copy
import math
from pathlib import Path

from .compile import compile as compile_doc
from .doc.fields import FIELDS
from . import fit_peaks as peaks

SHORT_OK = 0.3                 # a render within this many dB under the target has reached it (the engine itself settles within 0.2)
STEP_DB = 0.1                  # the search stops at this fineness
MAX_LIMIT = next(f.max for f in FIELDS["master"] if f.name == "maxLimit")
SMALL_RAISE = 1.0        # raising maxLimit by this much is still a gentle master
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
    while (got := measure(hi)) >= SHORT_OK:
        if hi >= cap or math.isinf(got):        # inf: past what the change may do at all; going further only gets worse
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


def _tame(goal, limit, short, r, root, engine, scratch, track=None):
    t = peaks.Tamer(root, engine, scratch, r)
    order = [w for w in ([track] if track else []) + peaks.peaked(r) if w in t.peak]
    order = list(dict.fromkeys(order))
    for n in range(1, min(peaks.MAX_TRACKS, len(order)) + 1):
        whos = order[:n]
        depth = solve(lambda d: t.measure(whos, d, goal), short, cap=peaks.MAX_DEPTH_DB, step=peaks.STEP_DB)
        if depth is None:
            continue
        if (tuple(whos), depth) not in t.seen:
            t.measure(whos, depth, goal)
        seen = t.seen[(tuple(whos), depth)]
        got, m = seen["got"], seen["got"].get("master") or {}
        names = " and ".join(whos)
        how = "; ".join(f"{w}: threshold {t.settings(w, depth)['threshold']:g} dB ({depth:g} dB under its peak), makeup {seen['makeup'][w]:+.1f} dB, "
                        f"kept {seen['drift'][w]:+.1f} dB from its place" for w in whos)
        return {"name": "tame_peaks", "tracks": whos, "depth_db": depth, "renders": t.renders, "lufs": round(got["lufs"], 2),
                "limit_db": round(m.get("limiterMaxReductionDb") or 0, 2), "ops": t.ops(whos, depth),
                "words": f"Reach {goal:g} LUFS inside the {limit:g} dB limit with the balance as written: a gentle compressor first on {names} "
                         f"(ratio {peaks.RATIO:g}:1, attack {peaks.ATTACK * 1000:g} ms, release {peaks.RELEASE * 1000:g} ms unless it has its own; {how}). "
                         f"Measured: {got['lufs']:.1f} LUFS, the limiter pulls {m.get('limiterMaxReductionDb') or 0:.1f} dB."}
    return {"name": "tame_peaks", "tracks": order[:peaks.MAX_TRACKS], "impossible": True, "renders": t.renders,
            "words": f"Taming up to {min(peaks.MAX_TRACKS, len(order))} of the most peaked tracks ({', '.join(order[:peaks.MAX_TRACKS])}) gently (at most "
                     f"{peaks.MAX_DEPTH_DB:g} dB under their peaks, {peaks.MAX_MAKEUP_DB:g} dB given back) does not reach the target within {limit:g} dB."}


def first_choice(need: float, limit: float) -> str:
    """The option to take first, from the last render alone: a raise of `maxLimit` by at most SMALL_RAISE dB is barely more
    limiting, so keep_balance; past that the master would stop being transparent, so tame the peaks (balance and limit both
    kept). trim_track moves the balance: never first."""
    return "keep_balance" if need - limit <= SMALL_RAISE and need <= MAX_LIMIT else "tame_peaks"


def best(options: list[dict], need: float, limit: float) -> dict | None:
    """The first choice when it is possible, else the next that is (keep_balance, tame_peaks, trim_track)."""
    ok = [o for o in options if o.get("ops")]
    return next((o for o in ok if o["name"] == first_choice(need, limit)), ok[0] if ok else None)


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
    options = [_keep_balance(goal, out["need_db"], limit), _tame(goal, limit, short, r, root, engine, scratch, track)]
    who = track or peakiest_track(r)
    if who in tracks:
        options.append(_trim(goal, limit, short, who, tracks, root, engine, scratch))
    pick = best(options, out["need_db"], limit)
    return {**out, "state": "under target", "short_db": round(short, 2), "options": options, "best": pick["name"] if pick else None,
            "words": f"The render landed {short:.1f} dB under the {goal:g} LUFS target: the limiter's need is {out['need_db']:g} dB and the master allows {limit:g}."}
