"""The engine's listening (`rostrum-sound analyze`, engine/src/analysis/analyze.rs): tempo, beats, downbeats, key,
chords, and the pitch and notes of a single line — the one source for all of them (`look_beats`, `look_pitch` and the
key of audio read it; there is no second beat tracker or pitch finder in Python).

Measured 2026-10-21 on three rendered songs (100 bpm D minor, 128 bpm Eb major, 84 bpm E minor): the engine named
all three keys (the Python chroma estimate missed two: F major, F minor) and all three tempos exactly. Its key names
come back with sharps ("D# major"); they are spelled here through the one speller (doc/keys.py).
Measured again 2026-10-21 (P12) after the engine's pitch finder moved to one FFT a frame: on the same three songs the
engine's beats sit 3–4 ms from the true beats (librosa: 15–97 ms), its notes start 6 ms off (pyin: 15–24 ms), all
notes right with cents; a 20 s part reads in 0.4 s (pyin 0.7–0.9 s, the engine before 6–8 s). A tempo drifting
100 → 120 BPM is followed (beats 4 ms off).
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path

import numpy as np
from rostrum_core import RostrumError, codes

from ..doc import keys
from ..engine import find_engine
from ..listen.core import load, mono, num
from ..listen.memo import remembered
from .theory import key_name

TIMEOUT_S = 300


@remembered
def analyze(wav, notes: bool = False, extra: tuple = ()) -> dict:
    """The engine's answer for a file (its mono mix): tempo, beats, key, chords, timbre, and notes with `notes`.
    `extra`: more engine options (`--pitch-only`, `--range lo hi`, `--beats-per-bar n`)."""
    y, sr = load(wav)
    with tempfile.TemporaryDirectory(prefix="rostrum-ears-") as tmp:
        raw = Path(tmp) / "mono.f32"
        np.asarray(mono(y), dtype="<f4").tofile(raw)
        cmd = [str(find_engine()), "analyze", str(raw), str(int(sr))] + (["--notes"] if notes else []) + [str(a) for a in extra]
        try:
            done = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:
            raise RostrumError(codes.INTERNAL, "engine analyze", str(wav), f"took over {TIMEOUT_S} s") from None
    if done.returncode != 0:
        raise RostrumError(codes.INTERNAL, "engine analyze", str(wav), done.stderr.strip() or f"exit {done.returncode}")
    return json.loads(done.stdout)


def spelled_key(name: str | None) -> str | None:
    """"D# major" -> "Eb major": the key by its usual spelling; None stays None."""
    p = keys.parse(name) if name else None
    return key_name(*p) if p and p[1] in ("major", "minor") else name


def key_of_audio(wav) -> dict:
    """The key estimate in the ears' form: {"key", "margin", "ranked": [(key, None) …]} (the runner-up when the
    engine names one; it gives a margin, not a score per key)."""
    k = analyze(wav)["key"]
    best, alt = spelled_key(k.get("name")), spelled_key(k.get("alternative"))
    return {"key": best, "margin": k.get("margin", 0.0), "ranked": [(x, None) for x in (best, alt) if x],
            "unsure": bool(k.get("unsure"))}


def beats(wav, beats_per_bar: int = 4) -> dict:
    """Facts about the pulse: bpm, how steady (`steadiness`: steady / drifting / uneven, from the beat spacing), every
    beat time (the engine follows a drifting tempo), the downbeats (the bar's beat where the lows land strongest) and
    how much stronger they land (`downbeat_confidence`, 1 = no lead)."""
    a = analyze(wav, extra=("--beats-per-bar", int(beats_per_bar)))
    b = np.asarray(a["beats"], dtype=float)
    out = {"duration_s": num(a["seconds"], 3), "beats_s": [num(x, 4) for x in b], "bpm": num(a["tempo"]["bpm"], 1),
           "tempo_alternatives": a["tempo"]["alternatives"], "tempo_unsure": a["tempo"]["unsure"]}
    if len(b) < 4:
        return {**out, "steadiness": "unknown", "downbeats_s": [], "downbeat_confidence": None,
                "note": "fewer than 4 beats found: no steady pulse to follow"}
    ibi = np.diff(b)
    bpm = 60.0 / ibi
    third = max(2, len(bpm) // 3)
    first, last = float(np.median(bpm[:third])), float(np.median(bpm[-third:]))
    cv = float(1.4826 * np.median(np.abs(ibi - np.median(ibi))) / np.median(ibi))     # robust: one missed beat is not unsteadiness
    change = (last - first) / first * 100
    steady = "steady" if cv < 0.05 and abs(change) < 3 else "drifting" if abs(change) >= 3 and cv < 0.15 else "uneven"
    return {**out, "bpm_start": num(first, 1), "bpm_end": num(last, 1), "bpm_change_pct": num(change, 1),
            "beat_spacing_variation": num(cv, 3), "steadiness": steady,
            "downbeats_s": [num(x, 4) for x in a["downbeats"]], "downbeat_confidence": a["downbeatConfidence"]}


def pitch(wav, fmin: float = 65.0, fmax: float = 1500.0):
    """The pitch of one line: (frame times, MIDI per frame with nan where unvoiced, frame length s, the notes as the
    engine split them: [start, length, midi, name, cents])."""
    a = analyze(wav, extra=("--pitch-only", "--range", float(fmin), float(fmax)))
    p = a["pitch"]
    midi = np.array([np.nan if m is None else m for m in p["midi"]], dtype=float)
    return p["first"] + np.arange(len(midi)) * p["hop"], midi, p["hop"], a["notes"]
