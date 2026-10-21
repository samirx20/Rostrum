"""Generated voice (rule 7: made once on request, stored by content): a line of text, a voice and a style become a
WAV in the content-keyed cache; every render reads that file. Qwen3-TTS 1.7B (Apache-2.0), the CustomVoice talker
at Q6_K, run by qwentts.cpp (MIT): one native program, so the model loads for the line and is released when the
process ends (docs: the experiment's docs/AI_MODELS.md › Voice; apps/sound/VOICE.md).

    take = voice.generate("The night is long.", voice="ryan", style="calm, close to the mic")
    take.file, take.seconds, take.generated            # generated=False: it was already in the cache

The model folder: ROSTRUM_QWENTTS_DIR, else ~/.rostrum/models/qwentts. ROSTRUM_TTS_DEVICE picks the device
("Vulkan0", "CPU" …). The cache entry follows shared/project-service/CONTRACT.md § 5 (key = SHA-256 of kind, engine
version, inputs, settings; written under a temporary name, then renamed; entry.json beside it) until the shared
cache lands in rostrum_core.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from rostrum_core import RostrumError, codes

VOICES = ("ryan", "aiden", "vivian", "serena", "uncle_fu", "dylan", "eric", "ono_anna", "sohee")
LANGUAGES = ("auto", "english", "chinese", "japanese", "korean", "german", "french", "russian", "portuguese",
             "spanish", "italian")
ENGINE = "qwen3-tts-1.7b-customvoice-q6k@qwentts-01b6127"   # bump when anything that decides the audio changes
EXE, CODEC, TALKER = "qwen-tts.exe" if os.name == "nt" else "qwen-tts", "qwen-tokenizer-12hz-Q8_0.gguf", \
    "qwen-talker-1.7b-customvoice-Q6_K.gguf"
MIN_FREE_GB = 2.5     # measured in the experiment: the talker peaks at 1.8-2.7 GB working set
TIMEOUT_S = 600


@dataclass
class Take:
    file: str
    seconds: float
    generated: bool
    key: str


def model_dir() -> Path:
    return Path(os.environ.get("ROSTRUM_QWENTTS_DIR") or Path.home() / ".rostrum" / "models" / "qwentts")


def cache_dir() -> Path:
    return Path(os.environ.get("ROSTRUM_CACHE_DIR") or Path.home() / ".rostrum" / "cache") / "voice"


def key(text: str, voice: str, style: str = "", language: str = "auto", seed: int = 1) -> str:
    recipe = {"kind": "ai.voice", "engine": ENGINE, "inputs": [text],
              "settings": {"voice": voice, "style": style, "language": language, "seed": seed}}
    return hashlib.sha256(json.dumps(recipe, sort_keys=True).encode()).hexdigest()[:32]


def cached(text: str, voice: str, style: str = "", language: str = "auto", seed: int = 1) -> Take | None:
    k = key(text, voice, style, language, seed)
    f = cache_dir() / k / "take.wav"
    return Take(str(f), _seconds(f), False, k) if f.is_file() else None


def generate(text: str, voice: str = "ryan", style: str = "", language: str = "auto", seed: int = 1) -> Take:
    """The line's take: from the cache, else generated once (loads the model, writes the cache, releases it)."""
    where = "voice"
    if not text.strip():
        raise RostrumError(codes.BAD_ARGUMENT, where, "text", "is empty")
    if voice not in VOICES:
        raise RostrumError.not_found(where, "voice", voice, VOICES, in_="the preset voices")
    if language not in LANGUAGES:
        raise RostrumError.not_found(where, "language", language, LANGUAGES, in_="the languages")
    hit = cached(text, voice, style, language, seed)
    if hit:
        return hit
    d = model_dir()
    missing = [n for n in (EXE, CODEC, TALKER) if not (d / n).is_file()]
    if missing:
        raise RostrumError(codes.MODEL_MISSING, where, "the voice model",
                           f"is not installed in {d} (missing {', '.join(missing)})")
    _memory_gate(where)
    k = key(text, voice, style, language, seed)
    entry = cache_dir() / k
    tmp = Path(tempfile.mkdtemp(prefix="rostrum-voice-"))
    try:
        out = tmp / "take.wav"
        args = [str(d / EXE), "--model", str(d / TALKER), "--codec", str(d / CODEC), "--speaker", voice,
                "--lang", language, "--seed", str(seed), "-o", str(out)]
        if style:
            args += ["--instruct", style]
        if os.environ.get("ROSTRUM_TTS_DEVICE"):
            args += ["--device", os.environ["ROSTRUM_TTS_DEVICE"]]
        t0 = time.perf_counter()
        try:
            p = subprocess.run(args, input=text.encode("utf-8"), capture_output=True, timeout=TIMEOUT_S)
        except subprocess.TimeoutExpired:   # run() ends the process it started before raising
            raise RostrumError(codes.JOB_FAILED, where, "voice generation", f"took longer than {TIMEOUT_S} s") from None
        took = time.perf_counter() - t0
        if p.returncode != 0:
            tail = " | ".join(p.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]) or f"exit {p.returncode}"
            raise RostrumError(codes.JOB_FAILED, where, "voice generation", f"failed: {tail}")
        seconds = _seconds(out)
        if seconds < 0.1:
            raise RostrumError(codes.JOB_FAILED, where, "voice generation", f'made no audio for "{text[:40]}"')
        part = entry.with_name(entry.name + ".partial")
        shutil.rmtree(part, ignore_errors=True)
        part.mkdir(parents=True)
        shutil.copyfile(out, part / "take.wav")
        (part / "entry.json").write_text(json.dumps({
            "kind": "ai.voice", "engine": ENGINE, "text": text, "voice": voice, "style": style, "language": language,
            "seed": seed, "seconds": seconds, "took": round(took, 2), "made": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "size": (part / "take.wav").stat().st_size}, indent=2), encoding="utf-8")
        shutil.rmtree(entry, ignore_errors=True)
        part.rename(entry)
        return Take(str(entry / "take.wav"), seconds, True, k)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _memory_gate(where):
    free = _free_gb()
    if free is not None and free < MIN_FREE_GB:
        raise RostrumError(codes.NO_MEMORY, where, "voice generation",
                           f"needs about {MIN_FREE_GB} GB of free memory; {free:.1f} GB is free")


def _free_gb():
    if os.name != "nt":
        return None
    import ctypes

    class M(ctypes.Structure):
        _fields_ = [("len", ctypes.c_ulong), ("load", ctypes.c_ulong), ("total", ctypes.c_ulonglong),
                    ("avail", ctypes.c_ulonglong), *[(f"x{i}", ctypes.c_ulonglong) for i in range(5)]]
    m = M()
    m.len = ctypes.sizeof(M)
    ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m))
    return m.avail / 2 ** 30


def _seconds(f: Path) -> float:
    with wave.open(str(f), "rb") as w:
        return w.getnframes() / w.getframerate()
