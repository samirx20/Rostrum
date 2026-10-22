"""Chords per bar or beat and the key, from the document's notes when it has any, else from the audio's chroma."""
from __future__ import annotations

import numpy as np

from ..doc import keys, tempo
from ..listen.core import load, mono, num
from ..listen.dsp import frames_to_time, resample
from ..listen.dsp_events import chroma
from .theory import chord_from_chroma, estimate_key, name_chord, relative_pair

MIN_SHARE = 0.15                # a pitch class counts in a window when it sounds for this share of it


def windows(root: dict, end: float, per: str) -> list[tuple[float, float, int, int]]:
    """(start, end, bar, beat in bar) per beat (or per bar) of the document's tempo map, up to `end` seconds."""
    bpb = int(root.get("beatsPerBar", 4))
    b = tempo.beats(root, end) + [end]
    step = bpb if per == "bar" else 1
    return [(b[i], min(b[min(i + step, len(b) - 1)], end), i // bpb + 1, i % bpb + 1)
            for i in range(0, len(b) - 1, step) if b[i] < end]


def chart_from_notes(notes, wins, key_at=lambda s: None) -> list[dict]:
    """The chord per window, chords and notes spelled in the key playing there (`key_at(seconds)`)."""
    rows = []
    for s, e, bar, beat in wins:
        key = key_at(s)
        weight: dict = {}
        for n in notes:
            over = min(e, n["end"]) - max(s, n["start"])
            if over > 0:
                for m in n["midis"]:
                    weight[m] = weight.get(m, 0) + over
        span = max(e - s, 1e-9)
        sounding = [m for m, w in weight.items() if w / span >= MIN_SHARE]
        low = min(sounding) if sounding else None
        chord = name_chord(sounding, low, key) if sounding else None
        rows.append({"bar": bar, "beat": beat, "start_s": num(s, 2),
                     "chord": chord or ("?" if len({m % 12 for m in sounding}) > 1 else keys.pitch_name(low, key) if sounding else "—"),
                     "notes": [keys.pitch_name(m, key) for m in sorted(sounding)]})
    return rows


def chroma_of(wav):
    """(chroma [12, frames], frame times) at 22.05 kHz, one frame per 2048 samples (dsp_events.chroma)."""
    y, sr = load(wav)
    c = chroma(resample(mono(y), sr, 22050), 22050, 2048)
    return c, frames_to_time(np.arange(c.shape[1]), 22050, 2048)


def chart_from_audio(chroma, t, wins, key_at=lambda s: None) -> list[dict]:
    rows = []
    for s, e, bar, beat in wins:
        sel = (t >= s) & (t < e)
        name, conf = chord_from_chroma(np.median(chroma[:, sel], axis=1) if sel.any() else np.zeros(12), key=key_at(s))
        rows.append({"bar": bar, "beat": beat, "start_s": num(s, 2), "chord": name, "confidence": conf})
    return rows


def speller(root: dict, given: str | None, est: dict):
    """seconds -> the key chords are spelled in there: the one asked for, else the document's key map, else the
    estimate."""
    return lambda s: given or keys.key_at(root, s) or est.get("key")


def key_from_notes(notes) -> dict:
    w = np.zeros(12)
    for n in notes:
        for m in n["midis"]:
            w[m % 12] += n["end"] - n["start"]
    return estimate_key(w)


def key_line(est: dict, source: str) -> str:
    if est["key"] is None:
        return "no key found"
    alt = next((k for k, _ in est["ranked"][1:] if relative_pair(est["key"], k)), None)
    said = f"{est['key']} (from {source}, margin {est['margin']})"
    return said + (f"; {alt} fits almost as well" if alt and est["margin"] < 0.1 else "")
