"""Notes of one melodic line, described: cents off, vibrato and drift from the pitch curve, the line's tuning, and
a comparison with the notes the document wrote. The pitch curve and the notes come from the engine (one pitch finder:
ears/engine_ears.py `pitch`); this file only reads them."""
from __future__ import annotations

import numpy as np

from ..doc.keys import pitch_name
from ..listen.core import num


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


def compare(written: list[dict], heard: list[dict], cents_tol: float = 25, time_tol: float = 0.06) -> dict:
    """Each written note against the heard note that overlaps it most: status ok / wrong_note / wrong_octave /
    late / early / out_of_tune / missing. Late and early are the start's offset in ms; out_of_tune is cents off
    the written pitch (a pitch bend or vibrato you wrote is not subtracted: read it with that in mind)."""
    rows = []
    for w in written:
        best = max(heard, key=lambda h: min(w["end"], h["end"]) - max(w["start"], h["start"]), default=None)
        over = 0 if best is None else min(w["end"], best["end"]) - max(w["start"], best["start"])
        label = "/".join(map(str, w["midis"]))
        row = {"id": w["id"], "written": label, "start_s": num(w["start"], 3), "target": w["midis"][0]}
        if best is None or over <= 0.02:
            rows.append({**row, "status": "missing"})
            continue
        target = min(w["midis"], key=lambda k: abs(k - best["midi"]))
        cents = (best["midi"] - target) * 100 + best["cents"]
        row |= {"target": target, "heard": best["note"], "start_off_ms": num((best["start"] - w["start"]) * 1000, 0), "cents_off": num(cents, 0)}
        if abs(best["midi"] - target) >= 1 and (best["midi"] - target) % 12 == 0:
            status = "wrong_octave"
        elif abs(best["midi"] - target) >= 1:
            status = "wrong_note"
        elif abs(row["start_off_ms"]) > time_tol * 1000:
            status = "late" if row["start_off_ms"] > 0 else "early"
        elif abs(best["cents"]) > cents_tol:
            status = "out_of_tune"
        else:
            status = "ok"
        rows.append({**row, "status": status})
    counts = {s: sum(r["status"] == s for r in rows) for s in sorted({r["status"] for r in rows})}
    return {"rows": rows, "counts": counts, "cents_tolerance": cents_tol, "time_tolerance_ms": time_tol * 1000}


def tuning_offset(heard: list[dict]) -> float | None:
    """The whole line's average cents from equal temperament, weighted by note length (a track tuned flat or sharp)."""
    if not heard:
        return None
    w = np.array([h["end"] - h["start"] for h in heard], dtype=float)
    return num(float(np.average([h["cents"] for h in heard], weights=w)), 1)
