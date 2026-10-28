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
from types import SimpleNamespace

from .compile import compile as compile_doc
from .doc.fields import FIELDS
from . import fit_peaks as peaks
from .trials import Trials

SHORT_OK = 0.3                 # a render within this many dB under the target has reached it (the engine itself settles within 0.2)
STEP_DB = 0.1                  # the search stops at this fineness
MAX_LIMIT = next(f.max for f in FIELDS["master"] if f.name == "maxLimit")
SMALL_RAISE = 1.0        # raising maxLimit by this much is still a gentle master
MAX_TRIM_DB = 12.0       # past this the track is all but gone: not an answer


def need_db(r: dict) -> float:
    """The limiting the target needs, in dB: what the limiter pulled in this render plus what was held down."""
    m = r.get("master") or {}
    return round((m.get("limiterMaxReductionDb") or 0) + (m.get("heldDb") or 0), 2)


LOT_DB = 3.0             # more limiting than this starts to flatten acoustic drums and piano
REACH_OK = 0.5           # a file within this of its target has reached it (what the Export sheet and the agents promise)


def _n(v: float) -> str:
    return f"{round(v, 1):g}".replace("-", "−")


def a_lot(db: float) -> str:
    """A word on how much limiting `db` is, for acoustic music ("" while it is gentle)."""
    if db <= LOT_DB:
        return ""
    return f" Over ~{LOT_DB:g} dB of limiting starts to flatten acoustic drums and piano."


def landing(master: dict, r: dict | None) -> dict:
    """Where a render of the song will land against the master's loudness target, from the last render `r`: the one
    prediction the Export sheet, the export and the agents' replies use. The limiter's need rises dB for dB with the
    gain the target asks, so with what it pulled (`limiterMaxReductionDb`) at the render's loudness, reaching the goal
    needs `pulled + goal - lufs` dB; gentle limiting holds it to `maxLimit` and the rest is left under the target.
    {target, lufs (predicted), need_db, limit, short_db, reaches, push (the master.set that reaches it, None when it
    already does or can't), impossible, words}. {} with no render or no target (nothing to predict)."""
    if not r or not isinstance(r.get("lufs"), (int, float)) or not master.get("normalize"):
        return {}
    goal = master.get("loudness", -16)
    m = r.get("master") or {}
    need = max(0.0, round((m.get("limiterMaxReductionDb") or 0) + goal - r["lufs"], 2))
    limit = master.get("maxLimit", 2) if master.get("gentle", True) else None
    short = max(0.0, need - limit) if limit is not None else 0.0
    lands = goal - short
    out = {"target": goal, "lufs": round(lands, 2), "need_db": need, "limit": limit, "short_db": round(short, 2),
           "reaches": short <= REACH_OK, "push": None, "impossible": False}
    if out["reaches"]:
        return {**out, "words": f"Will land at {_n(goal)} LUFS with {need:.1f} dB of limiting." + a_lot(need)}
    kb = _keep_balance(goal, need, limit)
    if kb.get("impossible"):
        return {**out, "impossible": True,
                "words": f"Will land at {_n(lands)} LUFS: reaching {_n(goal)} needs {need:.1f} dB of limiting, more than the {MAX_LIMIT:g} dB "
                         f"the master can do; the file stays there unless the peakiest track is turned down or tamed."}
    return {**out, "push": {"max_limit_db": kb["max_limit_db"], "ops": [{**kb["ops"][0], "args": {"maxLimit": kb["max_limit_db"], "gentle": True}}]},
            "words": f"Will land at {_n(lands)} LUFS: reaching {_n(goal)} needs {need:.1f} dB of limiting (Most limiting allows {limit:g})."
                     + a_lot(need)}


def reach(doc, engine, scratch: Path, span=None, most: int = 4) -> dict:
    """The `maxLimit` that lands this song on its master's loudness target, measured on the song as it is now (never
    predicted from another render): the song is measured, then each try at the limit it says it needs, until it lands
    within SHORT_OK of the target (the need grows faster than dB for dB under deep limiting: a peaky solo piano), or the
    master's top MAX_LIMIT. {} when there is no target to push to or the song already reaches it; else
    {max_limit_db, was_db, target, lufs, limit_db, reaches, renders, ops, words}. `doc`: anything with `data` (and
    `folder`, for the project's markers); never changed. `span`: the exported stretch, measured alone."""
    data = copy.deepcopy(doc.data)
    m = (data.get("master") or [{}])[0]
    if not (m.get("normalize") and m.get("gentle", True)):
        return {}
    goal, was = m.get("loudness", -16), m.get("maxLimit", 2)
    trials = Trials(engine, scratch, span)
    view = SimpleNamespace(data=data, folder=getattr(doc, "folder", None))

    def try_at(limit):
        m["maxLimit"] = limit
        return trials.one(compile_doc(view))
    r = try_at(was)
    land = landing(m, r)
    if not land or land["reaches"]:
        return {}
    ask = land["push"]["max_limit_db"] if land.get("push") else MAX_LIMIT
    for _ in range(most):
        r = try_at(ask)
        short = goal - r["lufs"]
        if short < SHORT_OK or ask >= MAX_LIMIT:
            break
        ask = min(MAX_LIMIT, math.ceil((ask + short + 0.05) * 10) / 10)
    lim = (r.get("master") or {}).get("limiterMaxReductionDb") or 0
    reaches = goal - r["lufs"] < REACH_OK
    words = (f"Most limiting raised to {ask:g} dB to reach {_n(goal)} LUFS" if reaches else
             f"Most limiting raised to {ask:g} dB, the most it goes: the file measures {_n(r['lufs'])} LUFS, under {_n(goal)}")
    return {"max_limit_db": ask, "was_db": was, "target": goal, "lufs": round(r["lufs"], 2), "limit_db": round(lim, 2),
            "reaches": reaches, "renders": trials.renders, "words": words + "." + a_lot(lim),
            "ops": [{"op": "master.set", "target": ["master"], "args": {"maxLimit": ask, "gentle": True}}]}


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


def solve(measure, short0: float, cap: float = MAX_TRIM_DB, step: float = STEP_DB, ahead=None):
    """The smallest trim (dB, to `step`) after which `measure(db)` -> how far under the target the render lands (dB) is
    under SHORT_OK; None when `cap` is not enough. The shortfall only falls as the trim grows: first try the shortfall
    itself, double until it is met, then halve. `ahead(dbs)` (a measure with no state between tries): the doubling
    tries measured side by side up front; the walk and the answer are the same."""
    lo, hi = 0.0, max(step, short0)
    if ahead:
        tries = [hi]
        while tries[-1] < cap:
            tries.append(min(tries[-1] * 2, cap))
        known, one = dict(zip(tries, ahead(tries))), measure
        measure = lambda d: known[d] if d in known else one(d)   # noqa: E731
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
            "words": f"Reach {goal:g} LUFS with the balance exactly as written: the limiter then pulls up to {ask:g} dB (now allowed: {limit:g})."
                     + a_lot(ask)}


def _trim(goal, limit, short, who, tracks, root, engine, scratch):
    trials = Trials(engine, scratch)

    def ahead(dbs):
        return [goal - got["lufs"] for got in trials.many([compile_doc(trimmed(root, who, db)) for db in dbs])]

    db = solve(lambda d: ahead([d])[0], short, ahead=ahead)
    if db is None:
        return {"name": "trim_track", "track": who, "impossible": True,
                "words": f"Lowering {who} by up to {MAX_TRIM_DB:g} dB does not reach the target within {limit:g} dB: the peaks come from more than {who} (pass `track` to try another)."}
    was = tracks[who].get("volume", 0.85)
    vol = trimmed_volume(tracks[who], db)
    return {"name": "trim_track", "track": who, "trim_db": db, "volume": vol, "was": was, "renders": trials.renders,
            "ops": [{"op": "track.set", "target": [who], "args": {"volume": vol}}],
            "words": f"Reach {goal:g} LUFS inside the {limit:g} dB limit by lowering {who} by {db:.1f} dB (volume {was:g} -> {vol:g}); the balance moves: "
                     f"{who} sits {db:.1f} dB lower against the rest."}


def _tame(goal, limit, short, r, root, engine, scratch, track=None):
    t = peaks.Tamer(root, engine, scratch, r)
    order = [w for w in ([track] if track else []) + peaks.peaked(r) if w in t.peak]
    order = list(dict.fromkeys(order))
    most = order[:peaks.MAX_TRACKS]
    if most and (far := t.probe(most, goal)) >= SHORT_OK and not math.isinf(far):   # known at once: the most it may tame is not enough
        return _untamed(goal, limit, most, t.renders, f" Even all {len(most)} at {peaks.MAX_DEPTH_DB:g} dB under their peaks land {far:.1f} dB under.")
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
        how = "; ".join(f"{w}: threshold {t.threshold(w, depth):g} dB ({t.peak[w] - t.threshold(w, depth):.1f} dB under its peak), makeup {seen['makeup'][w]:+.1f} dB, "
                        f"kept {seen['drift'][w]:+.1f} dB from its place" for w in whos)
        return {"name": "tame_peaks", "tracks": whos, "depth_db": depth, "renders": t.renders, "lufs": round(got["lufs"], 2),
                "limit_db": round(m.get("limiterMaxReductionDb") or 0, 2), "ops": t.ops(whos, depth),
                "words": f"Reach {goal:g} LUFS inside the {limit:g} dB limit with the balance as written: a gentle compressor first on {names} "
                         f"(ratio {peaks.RATIO:g}:1, attack {peaks.ATTACK * 1000:g} ms, release {peaks.RELEASE * 1000:g} ms unless it has its own; {how}). "
                         f"Measured: {got['lufs']:.1f} LUFS, the limiter pulls {m.get('limiterMaxReductionDb') or 0:.1f} dB."}
    return _untamed(goal, limit, most, t.renders)


def _untamed(goal, limit, most, renders, why=""):
    return {"name": "tame_peaks", "tracks": most, "impossible": True, "renders": renders,
            "words": f"Taming up to {len(most)} of the most peaked tracks ({', '.join(most)}) gently (at most "
                     f"{peaks.MAX_DEPTH_DB:g} dB under their peaks, {peaks.MAX_MAKEUP_DB:g} dB given back) does not reach the target within {limit:g} dB.{why}"}


def first_choice(need: float, limit: float) -> str:
    """The option to take first, from the last render alone: a raise of `maxLimit` by at most SMALL_RAISE dB that ends at
    no more than LOT_DB of limiting is barely more, so keep_balance; past that the master would stop being transparent
    (over LOT_DB flattens acoustic drums and piano), so tame the peaks (balance and limit both kept). trim_track moves the
    balance: never first."""
    return "keep_balance" if need - limit <= SMALL_RAISE and need <= min(MAX_LIMIT, LOT_DB) else "tame_peaks"


def best(options: list[dict], need: float, limit: float) -> dict | None:
    """The first choice when it is possible, else the next that is (keep_balance, tame_peaks, trim_track)."""
    ok = [o for o in options if o.get("ops")]
    return next((o for o in ok if o["name"] == first_choice(need, limit)), ok[0] if ok else None)


def _alone(name: str, search) -> dict:
    """One option's search; its failure is that option's "impossible" with the reason, never the whole plan's (a
    tame_peaks that can't be worked out still leaves keep_balance and trim_track to choose)."""
    try:
        return search()
    except Exception as e:   # noqa: BLE001 - any failure of this one search; the others stand
        return {"name": name, "impossible": True, "failed": str(e), "words": f"Could not be worked out here ({e}); the other options stand."}


def plan(r: dict, master: dict, tracks: dict, root: dict, engine, scratch: Path, track: str | None = None, only: str | None = None) -> dict:
    """The options for the last render `r`. `master`: the document's master fields; `tracks`: {id: track}.
    `only="keep_balance"`: just that option (no search renders)."""
    goal = master.get("loudness") if master.get("normalize") else None
    limit = master.get("maxLimit", 2) if master.get("gentle") else None
    out = {"target": goal, "lufs": r["lufs"], "need_db": need_db(r), "max_limit": limit}
    if goal is None:
        return {**out, "state": "no target", "best": "set_target", "words": "The master has no loudness target (normalize is off): the level is what the faders add up to. "
                         "Turn it on with edit_loudness {\"apply\": \"best\"} (or master(loudness=-16) in a script; "
                         "edit_document's op is master.set with target [\"master\"]), render_mix again, then fit.",
                "options": [{"name": "set_target", "words": "Turn the loudness target on.",
                             "ops": [{"op": "master.set", "target": ["master"], "args": {"normalize": True, "loudness": master.get("loudness", -16)}}]}]}
    short = goal - r["lufs"]
    if limit is None or short < SHORT_OK:
        return {**out, "state": "on target", "words": f"The render is on the {goal:g} LUFS target ({r['lufs']:.1f}); nothing to fit.", "options": []}
    options = [_keep_balance(goal, out["need_db"], limit)]
    if only != "keep_balance":                   # keep_balance needs no render: asking only for it never waits on the searches
        options.append(_alone("tame_peaks", lambda: _tame(goal, limit, short, r, root, engine, scratch, track)))
        who = track or peakiest_track(r)
        if who in tracks:
            options.append(_alone("trim_track", lambda: _trim(goal, limit, short, who, tracks, root, engine, scratch)))
    pick = best(options, out["need_db"], limit)
    return {**out, "state": "under target", "short_db": round(short, 2), "options": options, "best": pick["name"] if pick else None,
            "words": f"The render landed {short:.1f} dB under the {goal:g} LUFS target: the limiter's need is {out['need_db']:g} dB and the master allows {limit:g}."}
