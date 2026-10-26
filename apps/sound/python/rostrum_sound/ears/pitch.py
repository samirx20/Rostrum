"""Notes of one melodic line, described: cents off, vibrato and drift from the pitch curve, the line's tuning, and
the written notes' statuses (each judged on its attack in attack.py; timing and tuning from the line). The pitch
curve and the notes come from the engine (one pitch finder: ears/engine_ears.py `pitch`); this file only reads them."""
from __future__ import annotations

import numpy as np

from ..doc.keys import pitch_name
from ..listen.core import num
from .attack import register


def describe_notes(t, midi, frame_s: float, found) -> list[dict]:
    """The engine's notes ([start, length, midi, name, cents]) with what the curve under each shows: start, end,
    note, cents (median, + sharp), vibrato {rate_hz, depth_cents} or None, drift_cents (change over the note,
    + rising)."""
    out = []
    for start, length, k, _name, cents in found:
        seg = midi[(t >= start) & (t < start + length)]
        d = _describe(start, start + length, int(k), seg, frame_s)
        d["cents"] = num(cents, 1)
        out.append(d)
    return out


def _describe(start, end, k, seg, frame_s):
    ok = ~np.isnan(seg)
    cents = (seg[ok] - k) * 100
    out = {"start": num(start, 3), "end": num(end, 3), "note": pitch_name(k), "midi": k, "cents": num(np.median(cents), 1),
           "vibrato": None, "drift_cents": None}
    cents = cents[2:-2] if len(cents) > 8 else cents           # the first and last frames are the move between notes
    if len(cents) >= 12:
        x = np.arange(len(cents)) * frame_s
        slope, icpt = np.polyfit(x, cents, 1)
        out["drift_cents"] = num(slope * x[-1], 0)
        if len(cents) >= 15:                                   # vibrato: a 4–8 Hz wobble left after the slope
            res = cents - (slope * x + icpt)
            spec = np.abs(np.fft.rfft(res * np.hanning(len(res)), 512))
            f = np.fft.rfftfreq(512, frame_s)
            band = (f >= 3.5) & (f <= 8.5)
            sinus = band.any() and np.sum(spec[band] ** 2) >= 0.5 * np.sum(spec[f >= 1.0] ** 2)    # a wobble, not a blip
            if sinus and np.std(res) * 2 ** 0.5 >= 12:
                out["vibrato"] = {"rate_hz": num(f[band][np.argmax(spec[band])], 1), "depth_cents": num((np.percentile(res, 95) - np.percentile(res, 5)) / 2, 0)}
    return out


def compare(track: str, rows: list[dict], heard: list[dict] | None, onset_ms: dict | None = None, cents_tol: float = 25,
            time_tol: float = 0.06) -> dict:
    """Statuses for the written notes judged on their attacks (attack.check): ok / wrong_octave / missing. On a
    one-voice part: late / early from the sound's own onset nearest each written start (`onset_ms`: start -> ms
    off, listen.onsets), and out_of_tune / wrong_note from the pitch line's note sounding through the attack (`heard`;
    a bend or vibrato you wrote is not taken off). Heard notes no written note starts in (ringing tails) never count."""
    reach = max(2 * time_tol, 0.12) * 1000                 # an onset further off is another note's, not this one's
    onset = {round(k, 3): v for k, v in (onset_ms or {}).items() if v is not None and abs(v) <= reach}
    out = []
    for r in rows:
        r = dict(r)
        octave = r.pop("octave")
        h = _through(heard, r["start_s"]) if heard else None
        other = h is not None and (h["midi"] - r["target"]) % 12 != 0
        off = onset.get(round(r["start_s"], 3))
        if octave is None or (octave and other):
            status = "wrong_note" if other else "missing"
            r["heard"] = h["note"] if other else None
        elif octave:
            status = "wrong_octave"
        else:
            status = "ok"
            r |= {"start_off_ms": off, "cents_off": None if h is None else h["cents"]}
            if off is not None and abs(off) > time_tol * 1000:
                status = "late" if off > 0 else "early"
            elif h is not None and abs(h["cents"]) > cents_tol:
                status = "out_of_tune"
        out.append({**r, "status": status})
    counts = {s: sum(r["status"] == s for r in out) for s in sorted({r["status"] for r in out})}
    return {"rows": out, "counts": counts, "register": register(track, rows), "cents_tolerance": cents_tol,
            "time_tolerance_ms": time_tol * 1000, "judged": "each written note on its attack (what is new just after "
            "it starts)" + ("; timing from the sound's onsets, tuning from the pitch line" if heard is not None else
                            "; timing and tuning only on one-voice parts")}


def _through(heard: list[dict], start: float, at: float = 0.08) -> dict | None:
    """The pitch line's note sounding `at` seconds after `start` (inside the attack window), if any."""
    return next((h for h in heard if h["start"] <= start + at < h["end"]), None)


def tuning_offset(heard: list[dict]) -> float | None:
    """The whole line's average cents from equal temperament, weighted by note length (a track tuned flat or sharp)."""
    if not heard:
        return None
    w = np.array([h["end"] - h["start"] for h in heard], dtype=float)
    return num(float(np.average([h["cents"] for h in heard], weights=w)), 1)
