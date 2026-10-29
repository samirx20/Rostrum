"""squash: a mix the master's limiter flattens to reach the loudness target, named, and a fault when one part plays exposed.

Canary task 7 (Haiku): "Export a -14 LUFS stereo mix" on a solo piano and a glockenspiel; the agent raised the master's
Most limiting to 9.6 dB, the render took 9.6 dB of limiting and the reply said only "Over ~3 dB of limiting starts to
flatten acoustic drums and piano". Nothing stopped it. Over LINE_DB (fit_loudness.LOT_DB) the render's check now reads
the limiter (listen/limiter.py: the engine's own gain curve, and the stems' shares to name who drives it) and says how
much, where and which part. A part carrying most of the signal where the limiter works (a solo piano, a voice, strings
alone) has its attacks flattened in plain hearing: `squashed_mix`, a fault. A dense mix shares the gain among many parts
(4–6 dB is an ordinary loud master there), so it is a fault only past DENSE_DB, where pumping and dulled attacks are
heard even in a full band.

The fix is said in the order that keeps the music: the quiet parts up (unless the brief asks for a quiet start, a quiet
ending or a build: lifting flattens what it asked for), then sustained parts where it is thin and the spiky part
tamed, then a lower target (unless the brief names its number). Numbers measured on this render where it is cheap."""
from __future__ import annotations

import math
import re

import numpy as np

from .. import brief
from . import arc  # noqa: F401  registers the brief's quiet_start / quiet_ending words
from .core import num

LINE_DB = 3.0          # fit_loudness.LOT_DB: more limiting than this starts to flatten acoustic drums and piano
DENSE_DB = 6.0         # a dense mix (no part over EXPOSED_PCT) is squashed past this
EXPOSED_PCT = 60.0     # a part carrying this much of the signal where the limiter works plays exposed
NEAR_DB = 8.0          # passing.RULES: a squashed mix within this may be kept, when the brief asks for a squashed sound
JOIN_S = 0.5           # stretches over the line this close together read as one
TOP_SPANS = 4

brief.register("squashed_mix", ["squashed", "squash", "brickwall", "brick wall", "brickwalled", "pumping", "pumps",
                                "slammed", "crushed", "smashed", "maximised", "maximized", "hard limited",
                                "heavily limited", "heavy limiting", "loudness war", "as loud as possible", "no dynamics"],
               "a heavily limited, squashed sound")
brief.register("big_build", ["build", "builds", "building", "build up", "builds up", "swell", "swells", "swelling",
                             "crescendo", "grows", "growing", "rises", "rising", "quiet to loud", "soft to loud"],
               "a build or swell")
_LUFS = re.compile(r"([-−–]|minus\s*)?\s*(\d+(?:\.\d+)?)\s*lufs", re.I)


def over_spans(curve, step=0.1) -> list[dict]:
    """The stretches where the limiter pulls over LINE_DB: [{from_s, to_s, max_db}], the TOP_SPANS longest, in time order."""
    red = np.asarray(curve if curve is not None else [], dtype=float)
    on = np.concatenate([[False], red > LINE_DB, [False]])
    edges = np.flatnonzero(on[1:] != on[:-1])
    spans = []
    for a, b in zip(edges[::2], edges[1::2]):
        if spans and (a - spans[-1][1]) * step <= JOIN_S:
            spans[-1][1] = b
        else:
            spans.append([a, b])
    rows = [{"from_s": num(a * step, 1), "to_s": num(b * step, 1), "max_db": num(red[a:b].max(), 1)} for a, b in spans]
    return sorted(sorted(rows, key=lambda r: r["from_s"] - r["to_s"])[:TOP_SPANS], key=lambda r: r["from_s"])


def _sounds(data) -> dict:
    """track id -> the sound it plays ("builtIn:piano"), from the document: three piano tracks are one exposed piano
    (canary re-run: keys, lead and bell all on the piano, 36 % each, passed a 5.5 dB squash as a dense mix)."""
    out = {}
    for t in (data or {}).get("tracks") or []:
        form = t.get("instrument")
        if t.get("id") and isinstance(form, str) and isinstance(t.get(form), str):
            out[t["id"]] = f"{form}:{t[form]}"
    return out


def lead(lim: dict, tracks, data=None) -> dict | None:
    """The sound that drives the limiter and its share (%) of the signal there, the tracks playing the same sound
    counted together: from the stems at the worst moments over the line when the render has them, else from the tracks'
    own meters (the highest peak's sound, its share of the energy). `data`: the document's data (which sound each
    track plays); without it each track is its own sound."""
    sound = _sounds(data)
    key = lambda tid: sound.get(tid, tid)   # noqa: E731
    rows = [w for w in lim.get("worst") or [] if (w.get("reduced_db") or 0) > LINE_DB and w.get("drivers")]
    if rows:
        led: dict = {}
        for w in rows:
            for d in w["drivers"]:
                led[key(d["track"])] = led.get(key(d["track"]), 0.0) + (d.get("share_pct") or 0.0)
        top = max(led, key=led.get)
        ids = sorted({d["track"] for w in rows for d in w["drivers"] if key(d["track"]) == top})
        return {"track": _named(top, ids), "share_pct": num(led[top] / len(rows), 0), "from": "stems"}
    live = [t for t in tracks or [] if isinstance(t.get("lufs"), (int, float)) and math.isfinite(t["lufs"]) and t["lufs"] > -70]
    if not live:
        return None
    energy: dict = {}
    for t in live:
        energy[key(t["id"])] = energy.get(key(t["id"]), 0.0) + 10 ** (t["lufs"] / 10)
    top = max(live, key=lambda t: t.get("peak") or 0)
    ids = [t["id"] for t in live if key(t["id"]) == key(top["id"])]
    crest = 20 * math.log10(max(top.get("peak") or 0, 1e-9) / max(top.get("rms") or 0, 1e-9)) if top.get("rms") else None
    return {"track": _named(key(top["id"]), ids), "share_pct": num(100 * energy[key(top["id"])] / sum(energy.values()), 0),
            "from": "meters", "crest_db": num(crest, 1) if crest is not None else None}


def _named(sound: str, ids: list) -> str:
    """"piano (keys, lead, bell)" for a sound several tracks play; the track's own name for one."""
    if len(ids) == 1:
        return ids[0]
    return f"{sound.split(':', 1)[-1]} ({', '.join(ids)})"


def _spans_said(spans) -> str:
    return ", ".join(f"{s['from_s']:g}–{s['to_s']:g} s" for s in spans)


def line(lim: dict | None, tracks, data=None) -> str:
    """One sentence for the reply when the limiter pulls over the line ("" otherwise)."""
    if not lim or (lim.get("max_db") or 0) <= LINE_DB:
        return ""
    spans = over_spans(lim.get("_curve"), lim.get("curve_step_s") or 0.1)
    who = lead(lim, tracks, data)
    by = f", driven by {who['track']} ({who['share_pct']:g} % of the signal there)" if who else ""
    where = f" over {LINE_DB:g} dB at {_spans_said(spans)}" if spans else ""
    return f" Limiter: up to {lim['max_db']:.1f} dB of gain reduction{where}{by}."


def _quiet(wav):
    """lift_quiet's own ride, read on this render (no extra render): (most dB, [(from_s, to_s)] lifted ≥ 0.5 dB)."""
    from ..lift_quiet import STEP_S, WINDOW_S, curve, peaks_db, thin
    from .core import load
    from .loudness import short_term
    y, sr = load(wav)
    times, lufs = short_term(y, sr, step=STEP_S, window=WINDOW_S)
    ride = curve(times, lufs, peaks=peaks_db(y, times, sr=sr))
    most = max((v for _, v in thin(ride)), default=0.0)
    spans, start = [], None
    for t, v in ride:
        if v >= 0.5 and start is None:
            start = t
        elif v < 0.5 and start is not None:
            spans.append((start, t))
            start = None
    if start is not None:
        spans.append((start, ride[-1][0] + STEP_S))
    return round(most, 1), [s for s in spans if s[1] - s[0] >= 1.0][:3]


def brief_lufs(data) -> float | None:
    """The loudness the brief names ("a -14 LUFS mix" -> -14), None when it names none."""
    m = _LUFS.search(brief.text(data))
    return -float(m.group(2)) if m else None


def fault(wav, lim: dict | None, song: dict | None) -> list[dict]:
    """[squashed_mix] when the limiter pulls over LINE_DB on an exposed part, or over DENSE_DB on a dense mix.
    `song`: {"tracks": the render's track meters, "data": the document's data (its brief and master)}."""
    if not lim or (lim.get("max_db") or 0) <= LINE_DB:
        return []
    song = song or {}
    who = lead(lim, song.get("tracks"), song.get("data"))
    exposed = bool(who and (who["share_pct"] or 0) >= EXPOSED_PCT)
    if not exposed and lim["max_db"] <= DENSE_DB:
        return []
    data = song.get("data") or {}
    try:
        most, quiet = _quiet(wav)
    except Exception:  # noqa: BLE001  a file the ears cannot read: the fault stands without the lift's numbers
        most, quiet = None, []
    spans = over_spans(lim.get("_curve"), lim.get("curve_step_s") or 0.1)
    master = (data.get("master") or [{}])[0]
    arc_asks = next((p for p in (brief.asks(data, k) for k in ("quiet_start", "quiet_ending", "big_build")) if p), None)
    return [{"kind": "squashed_mix", "at_s": 0.0, "measured": {
        "reduced_db": lim["max_db"], "spans": spans, "seconds_over": num(sum(s["to_s"] - s["from_s"] for s in spans), 1),
        "lead": who and who["track"], "share_pct": who and who["share_pct"], "crest_db": who and who.get("crest_db"),
        "exposed": exposed, "lift_db": most, "quiet": [[num(a, 1), num(b, 1)] for a, b in quiet], "arc_asks": arc_asks,
        "target": master.get("loudness") if master.get("normalize") else None, "brief_lufs": brief_lufs(data)}}]


def words(f) -> str:
    d = f["measured"]
    over = d["reduced_db"] - LINE_DB
    who = d.get("lead")
    alone = (f"{who} carries {d['share_pct']:g} % of the signal there, so its attacks are flattened in plain hearing" if d["exposed"] else
             f"the parts share it (the most, {who}, {d['share_pct']:g} %), but past {DENSE_DB:g} dB even a full mix pumps") if who else ""
    where = f" over {LINE_DB:g} dB at {_spans_said(d['spans'])}" if d.get("spans") else ""
    what = (f"the master limiter squashes the mix: up to {d['reduced_db']:.1f} dB of gain reduction{where}" + (f", {alone}" if alone else "")
            + f" (passes at {LINE_DB:g} dB or less, fine to leave only when the brief asks for a squashed sound)")
    quiet = ", ".join(f"{a:g}–{b:g} s" for a, b in d.get("quiet") or [])
    if d.get("lift_db"):
        lift = (f"raise the quiet parts: on this render edit_loudness lift_quiet would ride {quiet or 'the quiet stretches'} up by "
                f"as much as {d['lift_db']:g} dB (it measures the limiting saved), or raise those parts' own volumes and velocities")
    else:
        lift = ("raise the quiet parts' own volumes and velocities (lift_quiet finds no stretch over 6 dB under the loudest "
                "to ride up here: the loud parts set the limiting)")
    drive = who or "the part that drives it"
    vel = f"velocities x{10 ** (-over / 40):.2f} take at least {over:.1f} dB off its peaks" if over > 0 else "lower velocities"
    crest = f" (its peaks stand {d['crest_db']:g} dB over its average)" if d.get("crest_db") else ""
    thick = (f"thicken where it is thin{' (' + quiet + ')' if quiet else ''}: sustained parts carry loudness without peaks "
             f"(a pad, held strings, the chords doubled an octave apart), and tame {drive}{crest}: lower its velocities "
             f"(recorded instruments fall at least as fast as velocity squared: {vel}) or edit_loudness tame_peaks measures a gentle compressor on it")
    if d.get("brief_lufs") is not None:
        lower = f"a lower target is not open: the brief fixes {d['brief_lufs']:g} LUFS, so the two above must get there"
    elif isinstance(d.get("target"), (int, float)):
        lower = (f"or, if the brief allows, a lower target: master(loudness={round(d['target'] - over):g}) needs about {LINE_DB:g} dB "
                 f"(each LU lower takes about a dB off the limiting)")
    else:
        lower = "or a lower loudness target, if the brief allows"
    if d.get("arc_asks"):
        steps = [thick, lower, f"not lifting the quiet parts: the brief asks for \"{d['arc_asks']}\", and a lift flattens it"]
    else:
        steps = [lift, thick, lower]
    return what + "; fix, in this order: " + "; ".join(f"({i}) {s}" for i, s in enumerate(steps, 1))
