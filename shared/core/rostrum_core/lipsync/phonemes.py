"""Phones of a voice clip, computed once and kept in the shared cache (kind "lipsync", an entry per audio content +
text + range + language + engine version). With the line's text: forced alignment (the known phones, placed where
the model hears them). Without: free decoding (the phones the model hears, any language).

    phonemes("take.wav", text="Every city keeps one hour.") -> [{"phone": "ɛ", "start": 0.12, "end": 0.16, "word": 0}, …]

Times are seconds in the file. A phone's end is where the model last hears it, which is often early (the model marks
a sound in one or two frames); `visemes.cues` decides how long a mouth holds.
"""
from __future__ import annotations

import json

from rostrum_core import RostrumError, codes
from rostrum_core.cache import CACHE, cache_key, file_hash

from . import audio, english, model

LANGUAGES = ("english",)      # with text; free decoding (no text) takes any language


def key(wav, start=0.0, end=None, text=None, language="english", pronounce=None) -> str:
    return cache_key("ai.lipsync", model.ENGINE, [file_hash(wav), text or ""],
                     {"start": start, "end": end, "language": language, "pronounce": pronounce or {}})


def analyse(wav, start: float = 0.0, end: float | None = None, text: str | None = None, language: str = "english",
            pronounce: dict | None = None, where: str = "lipsync", progress=None) -> dict:
    """The whole result: phones, words (with text), the device and how it was made. From the cache when there.
    `progress(step, of, words, fraction)`: 1 of 3 reading the voice, 2 listening (the model; `fraction` of the audio
    heard), 3 placing the phones. Called from the thread that works (a screen hands it over to its own)."""
    if text and language not in LANGUAGES:
        raise RostrumError.not_found(where, "language", language, LANGUAGES, in_="the languages with a dictionary")
    k = key(wav, start, end, text, language, pronounce)
    entry = CACHE.get("lipsync", k)
    if entry is None:
        recipe = {"engine": model.ENGINE, "wav": str(wav), "text": text, "start": start, "end": end,
                  "language": language}
        entry = CACHE.put("lipsync", k, lambda tmp: _make(tmp, wav, start, end, text, pronounce, where, progress), recipe)
        made = True
    else:
        made = False
    return {**json.loads((entry / "phones.json").read_text(encoding="utf-8")), "computed": made, "key": k}


def phonemes(wav, start: float = 0.0, end: float | None = None, text: str | None = None,
             language: str = "english", pronounce: dict | None = None) -> list[dict]:
    return analyse(wav, start, end, text, language, pronounce)["phones"]


def _make(tmp, wav, start, end, text, pronounce, where, progress=None):
    say = progress or (lambda *a: None)
    say(1, 3, "Opening the voice", 0.0)
    samples, total = audio.clip(wav, start, end, where)
    said = english.words(text, pronounce, where) if text else None
    if said == []:
        raise RostrumError(codes.BAD_ARGUMENT, where, "text", "has no words")
    labels = model.vocab(where)
    say(2, 3, "Listening to the line", 0.0)
    logp, device = model.emissions(samples, where, lambda f: say(2, 3, "Listening to the line", f),
                                   waiting=(lambda w: say(2, 3, w[:1].upper() + w[1:], 0.0)) if progress else None)
    say(3, 3, "Placing the mouth shapes", 0.0)
    phones = _aligned(logp, said, labels, where) if said else _decoded(logp, labels)
    for p in phones:
        p["start"], p["end"] = round(start + p["start"], 3), round(start + p["end"], 3)
    words = [{"word": w, "start": min(p["start"] for p in phones if p.get("word") == i),
              "end": max(p["end"] for p in phones if p.get("word") == i)} for i, (w, _) in enumerate(said or [])]
    out = {"engine": model.ENGINE, "device": device, "mode": "aligned" if said else "decoded",
           "start": start, "end": total if end is None else end, "phones": phones, "words": words}
    (tmp / "phones.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


def _aligned(logp, said, labels, where) -> list[dict]:
    from .ctc import align
    flat = [(i, u) for i, (_, us) in enumerate(said) for u in us]
    missing = sorted({u.ipa for _, u in flat if u.ipa not in labels})
    if missing:
        raise RostrumError(codes.JOB_FAILED, where, "the phone table", f"has labels the model lacks: {missing}")
    try:
        spans = align(logp, [labels[u.ipa] for _, u in flat], labels["<pad>"])
    except ValueError as e:
        raise RostrumError(codes.BAD_ARGUMENT, where, "the text", f"does not fit the audio: {e}",
                           hint="Is it the right take and range? Give the words that are said in it.") from e
    return [{"phone": u.ipa, "arpabet": " ".join(u.arpabet), "word": i, "start": a * model.FRAME_S,
             "end": (b + 1) * model.FRAME_S} for (i, u), (a, b) in zip(flat, spans)]


def _decoded(logp, labels) -> list[dict]:
    from .ctc import decode
    name = {v: k for k, v in labels.items()}
    return [{"phone": name[lab], "start": a * model.FRAME_S, "end": (b + 1) * model.FRAME_S}
            for lab, a, b in decode(logp, labels["<pad>"]) if not name[lab].startswith("<")]
