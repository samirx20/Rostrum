"""fault_shape: Sound's faults in the shared reply shape (rostrum_core.mcp.faults: {id, what, when, fix}), and the four
checks a weak agent shipped past: loudness off the target, a duck you cannot hear under a voice, a marked moment
with nothing starting on it, and sound still going past the song's end.

The existing faults ({kind, at_s, measured, words}, faults.py) keep their words and data; `shape` only renames them:
`id` is stable across re-runs (the kind, plus the marker's name when one sits at that time, else the time), `what` is
the measured part of the words, `fix` the rest. A marker's own notes do not exist in the document (a marker is a name,
a time and a colour), so "a marker meant as a sync point" is a marker whose name asks for a moment (hit, stop, drop,
climax, lift, drums back ...; weakest.NAMES): `no_<kind>` = nothing starts within 30 ms of it."""
from __future__ import annotations

import numpy as np
from rostrum_core.mcp import faults as shared

from .. import dialogue
from .core import db, load

LOUD_LU = 0.5          # the mix this far off the master's loudness target is a fault
DUCK_MIN_DB = 3.0      # a duck under a voice dipping less than this cannot be heard
END_AFTER_S = 0.1      # sound is read from this long after the declared end ...
END_WINDOW_S = 0.5     # ... for this long
END_DBFS = -50.0       # ... above this is still sounding


def _name_at(doc, t: float) -> str | None:
    try:
        from ..doc import markers
        with markers.project(getattr(doc, "folder", None)):
            return markers.at_time(doc.data, t, 0.05)
    except Exception:  # noqa: BLE001  a marker that does not resolve is the document checks' business
        return None


def shape(found: list[dict], doc) -> list[dict]:
    """The existing faults as shared faults."""
    out = []
    for f in found:
        k, t = f["kind"], f.get("at_s") or 0.0
        whole = k in ("held_tone", "near_mono", "dull_top", "leading_silence", "off_tempo") or not t
        mark = None if whole else _name_at(doc, t)
        if k.startswith("no_") and mark:
            fid = f"marker_onset:{mark}"
        else:
            fid = k if whole else f"{k}:{mark}" if mark else f"{k}@{t:g}"
        what, _, fix = f["words"].partition("; ")
        fix = fix[5:] if fix.startswith("fix: ") else fix          # the old words say "; fix: …" themselves
        when = None if whole else f"{t:.2f} s" + (f", marker '{mark}'" if mark else "")
        out.append(shared.fault(fid, what, fix or "see what", when))
    return out


def loudness_fault(measured, target, push=None) -> list[dict]:
    """The mix off the master's loudness target (`target` None: no target, nothing to miss) by more than LOUD_LU."""
    if not isinstance(target, (int, float)) or measured is None or abs(measured - target) <= LOUD_LU:
        return []
    short = measured < target
    raise_to = f"raise master maxLimit to {push:g} (in a script master(maxLimit={push:g}))" if push else "raise master maxLimit"
    fix = (f"{raise_to} (edit_loudness {{\"apply\": \"best\"}} measures it) or the quietest parts' volumes to gain "
           f"{target - measured:.1f} dB" if short else
           f"lower the master volume or loudness target by {measured - target:.1f} dB (a mix this far over the target is over-limited)")
    return [shared.fault("loudness", f"{measured:.1f} LUFS, the target is {target:g} ({measured - target:+.1f} LU, over {LOUD_LU:g} allowed)", fix)]


VOICE_DBFS = -45.0     # a 50 ms window of the voice's stem above this is speaking
_WIN_S = 0.05


def _speaking(stems: dict | None, ids) -> list[float] | None:
    """The start times of the 50 ms windows where any of the `ids` stems is above VOICE_DBFS (None: no stem to read)."""
    files = [stems[i] for i in ids or [] if stems and stems.get(i)]
    if not files:
        return None
    on = set()
    for f in files:
        y, sr = load(f)
        m = np.asarray(y, dtype=np.float64).reshape(len(y), -1).mean(axis=1)
        n = int(_WIN_S * sr)
        for k in range(len(m) // n):
            if db(float(np.mean(m[k * n:(k + 1) * n] ** 2))) > VOICE_DBFS:
                on.add(round(k * _WIN_S, 2))
    return sorted(on)


def _mean_dip(spans, speaking: list[float]) -> float:
    """The dip averaged over the time the voice speaks: a duck that fires in short blips lowers the music only there."""
    if not speaking:
        return 0.0
    got = [next((-sp[2] for sp in spans if sp[0] <= t < sp[1]), 0.0) for t in speaking]
    return max(0.0, sum(got) / len(got))


def duck_faults(data: dict, ducks: list | None, stems: dict | None = None) -> list[dict]:
    """A track's duck (under a voice, a voice-over clip or anything else) whose dip, averaged over the time the voice
    speaks (its stem above VOICE_DBFS), is under DUCK_MIN_DB; without the voice's stem, its deepest dip.
    `ducks`: the render's [{"track", "spans": [[from, to, db]]}] (the engine's own measured dips); `stems`: {track: wav}."""
    seen = {d["track"]: d.get("spans") or [] for d in ducks or []}
    out = []
    for t in data.get("tracks", []):
        mine = list(t.get("ducks", []))          # every duck: one under a voice-over clip (no lines, no `voice`) is the case that shipped silent
        if not mine:
            continue
        spans = seen.get(t["id"], [])
        speaking = _speaking(stems, dialogue.under_of(mine[0], t["id"], data.get("tracks", [])))   # empty: every dialogue track
        dip = _mean_dip(spans, speaking) if speaking is not None else max(0.0, -min((s[2] for s in spans), default=0.0))
        if dip < DUCK_MIN_DB:
            d = mine[0]
            said = (f"{len(spans)} dip{'s' * (len(spans) != 1)} covering {sum(b - a for a, b, _ in spans):.1f} s of {len(speaking) * _WIN_S:.1f} s of speech"
                    if speaking is not None else f"{len(spans)} dips" if spans else "no dips")
            out.append(shared.fault(
                f"duck:{t['id']}", f"{t['id']} is lowered {dip:.1f} dB on average while the voice speaks ({said}; under {DUCK_MIN_DB:g} dB cannot be heard)",
                f"raise the duck's depth (now {d.get('depth', 0.5):g}) and its hold/release so it stays down between words "
                "(voice=True ducks whole lines), or lower the track with volume keys under the voice's span", None))
    return out


def end_second(doc) -> float | None:
    """The song's declared end in seconds: its length, else a marker named "end"."""
    try:
        from ..doc import markers, times
        with markers.project(getattr(doc, "folder", None)):
            if doc.data.get("length") is not None:
                return times.seconds(doc.data["length"], doc.data, "length")
            return next((s for n, s in markers.all(doc.data) if n.strip().lower() == "end"), None)
    except Exception:  # noqa: BLE001
        return None


def rings_past_end(wav, end_s) -> list[dict]:
    """Sound above END_DBFS in the END_WINDOW_S that starts END_AFTER_S after the declared end (nothing to read when the
    file stops at it)."""
    if not end_s:
        return []
    y, sr = load(wav)
    a, b = int((end_s + END_AFTER_S) * sr), int((end_s + END_AFTER_S + END_WINDOW_S) * sr)
    if a >= len(y):
        return []
    seg = np.asarray(y[a:b], dtype=np.float64).reshape(len(y[a:b]), -1)
    level = db(float(np.mean(seg ** 2, axis=0).max()))
    if level <= END_DBFS:
        return []
    return [shared.fault("rings_past_end", f"still sounding {level:.0f} dBFS (above {END_DBFS:g}) after the end at {end_s:.2f} s",
                         "end the notes and tails before the end (shorter last notes, a fade on the master, "
                         "a shorter reverb tail) or move the end (length / an 'end' marker) later", f"{end_s + END_AFTER_S:.2f} s on")]


PEAK_SLACK_DB = 0.05   # the true-peak reading's own rounding


def peak_faults(peak, clipped) -> list[dict]:
    """The file's true peak over the master's ceiling (`peak` = (measured, ceiling)), and samples cut flat."""
    out = []
    tp, ceiling = peak or (None, None)
    if tp is not None and ceiling is not None and tp > ceiling + PEAK_SLACK_DB:
        out.append(shared.fault("true_peak", f"true peak {tp:.1f} dBTP, over the {ceiling:g} ceiling",
                                "keep the master limiter on (it holds the ceiling) or lower the loudest track; edit_loudness tame_peaks"))
    if clipped:
        out.append(shared.fault("clipped", f"{clipped} samples cut flat at full scale",
                                "lower the master volume or the track driving it; keep the limiter on"))
    return out


def all_faults(doc, found, wav, measured_lufs, target, ducks, stems=None, ring_s=0.0, peak=None, clipped=None, push=None) -> list[dict]:
    """Every check, shaped: the listening faults, then loudness, the file's peak and clipping, ducks and the end (the
    end read after the ring a render allowed: ring_past_length)."""
    out = (shape(found, doc) + loudness_fault(measured_lufs, target, push) + peak_faults(peak, clipped)
           + duck_faults(doc.data, ducks, stems))
    try:
        end = end_second(doc)
        out += rings_past_end(wav, end + ring_s if end else end)
    except Exception:  # noqa: BLE001  a file the ears cannot read is said by the listening check
        pass
    return out
