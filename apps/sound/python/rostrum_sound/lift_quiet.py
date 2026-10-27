"""lift_quiet: ride the quiet parts up instead of limiting the loud ones (a mastering engineer's slow fader ride).

Reaching a streaming target on music with real dynamics (a soft intro, a crescendo, a loud climax) raises the whole
mix until the climax hits the limiter: the quiet parts set how much, the loud parts pay for it. Lifting the quiet
parts a few dB before the target is reached raises the song's loudness without raising its peaks, so the limiter
pulls less. The ride is the master's own volume lane, in plain sight and editable like any other automation; the
order of loud and soft never changes (a crescendo stays a crescendo, only its soft end comes up a little).

The ride, from the last render's short-term loudness (3 s windows, every half second): every moment more than `keep_db`
under the loudest is raised by `share` of the distance (half, by default), never more than `most_db`; moments near
silence (a fade, the ring-out) take the lift of the music beside them, so an ending's tail is never pumped up on its
own. The lift moves slowly (it changes by at most RATE_DB a second), and the lane keeps only the points it needs."""
from __future__ import annotations

import copy
import math
from types import SimpleNamespace

import numpy as np

from .compile import compile as compile_doc
from .listen.core import load
from .listen.loudness import short_term
from .doc import ids
from .trials import Trials
from . import fit_loudness as fit

STEP_S = 0.5                 # the loudness is read this often
WINDOW_S = 3.0               # over this long (short-term loudness, EBU R128)
KEEP_DB = 6.0                # moments within this of the loudest are left as they are
SHARE = 0.5                  # how much of a quiet part's distance under KEEP_DB is lifted
MOST_DB = 4.0                # the most any moment is raised
SILENT_DB = 25.0             # quieter than this under the loudest: near silence, not music to lift
RATE_DB = 1.5                # the lift changes by at most this many dB a second (a slow ride, never a pump)
PEAK_ROOM_DB = 1.0           # a lifted passage's peaks stay this far under the song's loudest
TOLERANCE_DB = 0.25          # a lane point is dropped when the line through its neighbours is this close


def peaks_db(y, times, window=WINDOW_S, sr=48000) -> np.ndarray:
    """The highest sample (dBFS) in each loudness window (ending at each of `times`)."""
    a = np.abs(y).max(axis=1) if y.ndim > 1 else np.abs(y)
    return np.array([20 * np.log10(max(float(a[max(0, int((e - window) * sr)):max(1, int(e * sr))].max(initial=0.0)), 1e-9))
                     for e in times])


def curve(times, lufs, keep_db=KEEP_DB, share=SHARE, most_db=MOST_DB, peaks=None) -> list[tuple[float, float]]:
    """[(seconds, lift dB)] for a short-term loudness reading (`times`: each window's end): the ride before it is thinned.
    `peaks` (dBFS, one a window): a lifted window's peaks stay PEAK_ROOM_DB under the song's loudest peak, so the lift
    never gives the limiter more to pull (a quiet passage with sharp attacks, a solo piano's, is lifted less or not)."""
    lufs = np.asarray(lufs, dtype=float)
    ok = np.isfinite(lufs)
    if not ok.any():
        return []
    top = float(lufs[ok].max())
    music = ok & (lufs > top - SILENT_DB)
    lift = np.where(music, np.clip((top - keep_db - lufs) * share, 0.0, most_db), np.nan)
    if peaks is not None:
        peaks = np.asarray(peaks, dtype=float)
        lift = np.where(music, np.minimum(lift, np.maximum(peaks.max() - PEAK_ROOM_DB - peaks, 0.0)), lift)
    idx = np.arange(len(lift))
    known = ~np.isnan(lift)
    if not known.any():
        return []
    lift = np.interp(idx, idx[known], lift[known])          # near silence: the lift of the music beside it
    at = np.maximum(np.asarray(times, dtype=float) - WINDOW_S / 2, 0.0)   # a window's reading belongs to its middle
    step = RATE_DB * STEP_S
    for i in range(1, len(lift)):                            # slow both ways: never faster than RATE_DB a second
        lift[i] = min(lift[i], lift[i - 1] + step)
    for i in range(len(lift) - 2, -1, -1):
        lift[i] = min(lift[i], lift[i + 1] + step)
    return [(round(float(t), 3), round(float(v), 2)) for t, v in zip(at, lift)]


def thin(pts: list[tuple[float, float]], tol=TOLERANCE_DB) -> list[tuple[float, float]]:
    """The fewest points whose straight lines stay within `tol` dB of `pts` (first and last kept)."""
    if len(pts) <= 2:
        return list(pts)
    out, a = [pts[0]], 0
    for b in range(2, len(pts)):
        (t0, v0), (t1, v1) = pts[a], pts[b]
        bad = any(abs(v0 + (v1 - v0) * (pts[k][0] - t0) / max(t1 - t0, 1e-9) - pts[k][1]) > tol for k in range(a + 1, b))
        if bad:
            a = b - 1
            out.append(pts[a])
    out.append(pts[-1])
    return out


def _lane(master: dict) -> list | None:
    return next((a["points"] for a in master.get("automation", []) if a.get("lane") == "volume"), None)


def _at(points, t, default):
    """The lane's value at `t` seconds (straight lines between points; numbers only)."""
    num = [(p[0], p[1]) for p in points or [] if isinstance(p[0], (int, float))]
    if not num:
        return default
    ts, vs = zip(*num)
    return float(np.interp(t, ts, vs))


def points(master: dict, ride: list[tuple[float, float]]) -> list[list[float]]:
    """The master's volume lane with the ride on top of its fader (or of its own lane, when it has one written in seconds)."""
    vol, lane = master.get("volume", 1), _lane(master)
    return [[t, round(min(4.0, _at(lane, t, vol) * 10 ** (db / 20)), 4)] for t, db in ride]


def plan(doc, render: dict, engine, scratch, keep_db=KEEP_DB, share=SHARE, most_db=MOST_DB) -> dict:
    """The ride for the song as last rendered (`render`: {file, lufs, master: {...}}), measured by the engine before it is
    offered: {lift_db (the most any moment rises), ops (one automation.set on the master's volume lane), need_before,
    need_after (dB of limiting the loudness target needs), renders, words}. `ops` is empty when nothing is quiet enough
    to lift. `doc`: anything with `data` (and `folder`); never changed."""
    y, sr = load(render["file"])
    times, lufs = short_term(y, sr, step=STEP_S, window=WINDOW_S)
    ride = thin(curve(times, lufs, keep_db, share, most_db, peaks_db(y, times, sr=sr)))
    most = max((v for _, v in ride), default=0.0)
    before = fit.need_db(render)
    if most < 0.5:
        return {"lift_db": 0.0, "ops": [], "need_before": before, "need_after": before, "renders": 0,
                "words": f"Nothing to lift: every part of the song is within {keep_db:g} dB of its loudest moment."}
    data = copy.deepcopy(doc.data)
    master = (data.get("master") or [{}])[0]
    pts = points(master, ride)
    if (lane := _lane(master)) is not None and any(not isinstance(p[0], (int, float)) for p in lane):
        return {"lift_db": 0.0, "ops": [], "need_before": before, "need_after": before, "renders": 0,
                "words": "The master's volume lane is written in bars or markers: lifting would replace it; change it there instead."}
    auto = [a for a in master.get("automation", []) if a.get("lane") != "volume"]
    master["automation"] = auto + [{"id": ids.lane("master", "volume"), "type": "automation", "lane": "volume", "points": pts}]
    got = Trials(engine, scratch).one(compile_doc(SimpleNamespace(data=data, folder=getattr(doc, "folder", None))))
    after = fit.need_db(got)
    quiet = sum(1 for _, v in ride if v >= 0.5)
    words = (f"Lift the quiet parts by up to {most:.1f} dB on the master's volume lane ({len(pts)} points; parts within "
             f"{keep_db:g} dB of the loudest stay as written, loud and soft keep their order, no lifted peak above the loudest): reaching the target then needs "
             f"{after:.1f} dB of limiting instead of {before:.1f}.")
    if quiet == 0 or after >= before - 0.2:
        words += " That barely helps here: the loud parts, not the quiet ones, set the limiting."
    return {"lift_db": round(most, 2), "need_before": before, "need_after": after, "renders": 1, "lufs_after": round(got["lufs"], 2),
            "ops": [{"op": "automation.set", "target": ["master"], "args": {"lane": "volume", "points": pts}}], "words": words}


def worth_it(need_db: float) -> bool:
    """Offer the lift only where limiting would start to flatten acoustic music."""
    return need_db > fit.LOT_DB and not math.isnan(need_db)
