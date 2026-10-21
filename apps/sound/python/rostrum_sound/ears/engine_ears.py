"""The engine's listening (`rostrum-sound analyze`, engine/src/analysis/analyze.rs): tempo, key, chords and notes of
a recording, the one source for the key of audio.

Measured 2026-10-21 on three rendered songs (100 bpm D minor, 128 bpm Eb major, 84 bpm E minor): the engine named
all three keys (the Python chroma estimate missed two: F major, F minor) and all three tempos exactly. Its key names
come back with sharps ("D# major"); they are spelled here through the one speller (doc/keys.py).
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
from ..listen.core import load, mono
from .theory import key_name

TIMEOUT_S = 300


def analyze(wav, notes: bool = False) -> dict:
    """The engine's answer for a file (its mono mix): tempo, key, chords, timbre, and notes with `notes`."""
    y, sr = load(wav)
    with tempfile.TemporaryDirectory(prefix="rostrum-ears-") as tmp:
        raw = Path(tmp) / "mono.f32"
        np.asarray(mono(y), dtype="<f4").tofile(raw)
        cmd = [str(find_engine()), "analyze", str(raw), str(int(sr))] + (["--notes"] if notes else [])
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
