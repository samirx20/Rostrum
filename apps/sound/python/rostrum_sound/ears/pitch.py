"""Pitch of one melodic line (librosa pyin): the notes it plays with times and cents off, vibrato and drift, and a
comparison with the notes the document wrote. pyin follows one note at a time: use it on a single-voice stem."""
from __future__ import annotations

import librosa
import numpy as np
from scipy.ndimage import median_filter

from ..listen.core import load, mono, num
from ..doc.keys import pitch_name
from .theory import hz_to_midi

SR = 22050
HOP = 441                      # 20 ms per pitch frame
FRAME_S = HOP / SR


def pitch_track(wav, fmin: float = 65.0, fmax: float = 1500.0):
    """(times, midi per frame with nan where nothing is voiced, voiced probability)."""
    y, sr = load(wav)
    m = librosa.resample(mono(y), orig_sr=sr, target_sr=SR) if sr != SR else mono(y)
    f0, _, prob = librosa.pyin(m, fmin=fmin, fmax=fmax, sr=SR, frame_length=2048, hop_length=HOP)
    midi = np.where(np.isnan(f0), np.nan, hz_to_midi(np.nan_to_num(f0, nan=440.0)))
    return librosa.times_like(f0, sr=SR, hop_length=HOP), midi, prob


def segment_notes(t, midi, min_len: float = 0.08, max_gap: int = 2) -> list[dict]:
    """Notes from a pitch track: runs of frames that stay on one nearest semitone (a median filter ignores blips).
    Each: start, end, note, cents (median, + sharp), vibrato {rate_hz, depth_cents} or None, drift_cents (change over
    the note, + rising), `contour` (the frame values the picture draws)."""
    voiced = ~np.isnan(midi)
    near = np.where(voiced, np.round(median_filter(np.nan_to_num(midi, nan=0.0), 5)), -1)
    notes, i, n = [], 0, len(midi)
    while i < n:
        if not voiced[i]:
            i += 1
            continue
        j, gap = i, 0
        while j + 1 < n and (near[j + 1] == near[i] or (not voiced[j + 1] and gap < max_gap)):
            gap = gap + 1 if not voiced[j + 1] else 0
            j += 1
        seg = midi[i:j + 1]
        seg = seg[~np.isnan(seg)]
        if len(seg) * FRAME_S >= min_len:
            notes.append(_describe(t[i], t[j] + FRAME_S, int(near[i]), midi[i:j + 1]))
        i = j + 1
    return notes


def _describe(start, end, k, seg):
    ok = ~np.isnan(seg)
    cents = (seg[ok] - k) * 100
    out = {"start": num(start, 3), "end": num(end, 3), "note": pitch_name(k), "midi": k, "cents": num(np.median(cents), 1),
           "vibrato": None, "drift_cents": None}
    cents = cents[2:-2] if len(cents) > 8 else cents           # the first and last frames are the move between notes
    if len(cents) >= 12:
        x = np.arange(len(cents)) * FRAME_S
        slope, icpt = np.polyfit(x, cents, 1)
        out["drift_cents"] = num(slope * x[-1], 0)
        if len(cents) >= 15:                                   # vibrato: a 4–8 Hz wobble left after the slope
            res = cents - (slope * x + icpt)
            spec = np.abs(np.fft.rfft(res * np.hanning(len(res)), 512))
            f = np.fft.rfftfreq(512, FRAME_S)
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
