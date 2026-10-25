"""Each spoken word's start and end (rule 7: heard once on request, stored by content, read many times).

A voice line's take is listened to by the speech model (Parakeet TDT v3 through sherpa-onnx, the captions model the
plan chose; CPU, loads for the take and is released) and each word gets a start and an end. The result is stored in
the shared cache keyed by the take's own key and this engine's version, so a take is heard once and a re-read never
runs the model. Times are stored from the take's start; `read` / `compute` answer in song seconds (the line's start
added), the same clock `render_voice` and 2D's voice-over row use.

    voice_words.compute(doc, ids=None)   # hear the lines that have not been heard yet; loud when a take is missing
    voice_words.read(doc, ids=None)      # stored words only (never runs the model); loud when a line was not heard
    -> [{id, track, text, start, end, words: [{word, start, end}], heard_now: bool}]  (heard_now False = from storage)
"""
from __future__ import annotations

import wave
from pathlib import Path
from typing import Callable

from rostrum_core import RostrumError, codes
from rostrum_core.cache import Cache, cache_key

from . import memory, settings, voice, voice_lines
from .doc import times

ENGINE = "parakeet-tdt-0.6b-v3-int8@sherpa-onnx-1.13"     # bump when anything that decides the words changes
FILES = ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt")
MIN_FREE_GB = 2.0
TAIL_S = 0.16            # a word lasts at least up to its last piece plus this, when no word follows soon


def model_dir() -> Path:
    import os
    return Path(os.environ.get("ROSTRUM_ASR_DIR") or settings.models_dir() / "parakeet-tdt-0.6b-v3")


def key_of(take: voice.Take) -> str:
    return cache_key("ai.words", ENGINE, [take.key], {})


def _stored(take: voice.Take) -> list[dict] | None:
    entry = Cache().get("voice-words", key_of(take))
    if not entry:
        return None
    import json
    return json.loads((entry / "words.json").read_text(encoding="utf-8"))["words"]


def _pieces_to_words(tokens: list[str], stamps: list[float], length: float) -> list[dict]:
    """The model's pieces (" The", " ni", "ght", " is": a space, or "▁", opens a word) and their start times as words
    with a start and an end."""
    words: list[list] = []
    for tok, t in zip(tokens, stamps):
        if tok[:1] in (" ", "▁") or not words:
            words.append([tok.lstrip(" ▁"), float(t), float(t)])
        else:
            words[-1][0] += tok
            words[-1][2] = float(t)
    out = []
    for i, (w, first, last) in enumerate(words):
        nxt = words[i + 1][1] if i + 1 < len(words) else length
        out.append({"word": w, "start": round(first, 3), "end": round(max(first, min(nxt, last + TAIL_S, length)), 3)})
    return [w for w in out if w["word"].strip()]


def _read_wav(path: str):
    import numpy as np
    with wave.open(path, "rb") as w:
        n, rate, width = w.getnchannels(), w.getframerate(), w.getsampwidth()
        raw = w.readframes(w.getnframes())
    if width != 2:
        raise RostrumError(codes.BAD_ARGUMENT, "voice words", f'take "{path}"', f"is {8 * width}-bit; expected 16-bit")
    data = np.frombuffer(raw, dtype="<i2").astype("float32") / 32768.0
    return (data.reshape(-1, n).mean(axis=1) if n > 1 else data), rate


def _runtime(where: str):
    """sherpa-onnx, the program that runs the speech model: a Python package, not a model file."""
    try:
        import sherpa_onnx
    except ImportError as e:
        import sys
        raise RostrumError(codes.MODEL_MISSING, where, "sherpa-onnx (the program that runs the speech model)",
                           "is not installed in the Python this app runs on",
                           hint=f'Install it with: "{sys.executable}" -m pip install sherpa-onnx==1.13.8 (Apache-2.0), '
                                "then call render_voice (what: words) again.") from e
    return sherpa_onnx


def recognise(wav: str) -> list[dict]:
    """Listen to a WAV: the words with start / end in seconds from its start. Loud when the model is missing, memory
    is short, or no word is heard."""
    where = "voice words"
    d = model_dir()
    missing = [n for n in FILES if not (d / n).is_file()]
    if missing:
        from .cleanup import fetch
        raise RostrumError(codes.MODEL_MISSING, where, "the speech model", f"is not installed in {d} (missing {', '.join(missing)})",
                           hint=fetch.next_step("speech"))
    sherpa_onnx = _runtime(where)
    memory.gate(where, "the speech model", MIN_FREE_GB)
    samples, rate = _read_wav(wav)
    rec = sherpa_onnx.OfflineRecognizer.from_transducer(
        encoder=str(d / FILES[0]), decoder=str(d / FILES[1]), joiner=str(d / FILES[2]), tokens=str(d / FILES[3]),
        num_threads=2, model_type="nemo_transducer", provider="cpu")
    stream = rec.create_stream()
    stream.accept_waveform(rate, samples)
    rec.decode_stream(stream)
    res = stream.result
    del rec                                          # the model is released with the recogniser
    words = _pieces_to_words(list(res.tokens), list(res.timestamps), len(samples) / rate)
    if not words:
        raise RostrumError(codes.JOB_FAILED, where, "the speech model", f"heard no words in {Path(wav).name}")
    return words


def _fit_text(words: list[dict], text: str) -> list[dict]:
    """When the model heard as many words as the line has, the line's own spelling is kept with the heard times."""
    own = text.split()
    return [{**w, "word": o} for w, o in zip(words, own)] if len(own) == len(words) else words


def _put(take: voice.Take, words: list[dict]) -> None:
    import json
    Cache().put("voice-words", key_of(take), lambda f: (f / "words.json").write_text(
        json.dumps({"words": words}, ensure_ascii=False), encoding="utf-8"), {"engine": ENGINE, "take": take.key})


def _line_row(root: dict, track: dict, ln: dict, words: list[dict], heard: bool) -> dict:
    start = times.seconds(ln["at"], root, f"line {ln['id']}")
    shifted = [{**w, "start": round(start + w["start"], 3), "end": round(start + w["end"], 3)} for w in words]
    return {"id": ln["id"], "track": track["id"], "text": ln["text"], "start": round(start, 3),
            "end": shifted[-1]["end"], "words": shifted, "heard_now": heard}


def compute(doc, ids=None, progress: Callable[[str], None] | None = None,
            listen: Callable[[str], list[dict]] = recognise) -> list[dict]:
    """Words of every line (or `ids`): stored ones as they are, the rest heard now and stored. A line whose take is
    not made fails loudly, naming the line (make it with render_voice first)."""
    root, out = getattr(doc, "data", doc), []
    for t, ln in voice_lines.lines(doc, ids):
        take = voice_lines.take_of(t, ln)
        if take is None:
            raise RostrumError(codes.NOT_FOUND, f"voice line {ln['id']}", f'voice line "{ln["id"]}"', "is not made yet",
                               hint="Run render_voice first; the words are heard from the made take.")
        words = _stored(take)
        heard = words is None
        if heard:
            if progress:
                progress(f'{ln["id"]}: listening to "{ln["text"][:40]}"')
            words = _fit_text(listen(take.file), ln["text"])
            _put(take, words)
        out.append(_line_row(root, t, ln, words, heard=heard))
    return out


def read(doc, ids=None) -> list[dict]:
    """Stored words only: never runs the model. A line not heard yet is a loud error that says how to hear it."""
    root, out = getattr(doc, "data", doc), []
    for t, ln in voice_lines.lines(doc, ids):
        take = voice_lines.take_of(t, ln)
        words = _stored(take) if take else None
        if words is None:
            raise RostrumError(codes.NOT_FOUND, f"voice line {ln['id']}", f'words of "{ln["id"]}"', "are not stored yet",
                               hint="Run the render_voice (what: words) tool (it hears the made take once and keeps the words).")
        out.append(_line_row(root, t, ln, words, heard=False))
    return out
