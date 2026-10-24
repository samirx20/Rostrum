"""English text → the phone aligner's labels. Words come from the CMU Pronouncing Dictionary (BSD-2) or the caller's
`pronounce` table; ARPAbet goes to IPA through our own table, written against the model's vocab.json. The model
tokenizer's text path (phonemizer / espeak-ng, GPL) is never used.

    words("Every city.") -> [("every", [Unit("ɛ", ["EH1"]), Unit("v", ["V"]), Unit("ɚ", ["ER0"]), Unit("i", ["IY0"])]), …]
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from rostrum_core import RostrumError, codes

from .model import models_dir

BASE = {"AA": "ɑː", "AE": "æ", "AO": "ɔː", "AW": "aʊ", "AY": "aɪ", "EH": "ɛ", "EY": "eɪ", "IH": "ɪ", "OW": "oʊ",
        "OY": "ɔɪ", "UH": "ʊ", "UW": "uː", "B": "b", "CH": "tʃ", "D": "d", "DH": "ð", "F": "f", "G": "ɡ", "HH": "h",
        "JH": "dʒ", "K": "k", "L": "l", "M": "m", "N": "n", "NG": "ŋ", "P": "p", "R": "ɹ", "S": "s", "SH": "ʃ",
        "T": "t", "TH": "θ", "V": "v", "W": "w", "Y": "j", "Z": "z", "ZH": "ʒ"}
STRESSED = {"AH": ("ə", "ʌ"), "ER": ("ɚ", "ɜː"), "IY": ("i", "iː")}      # (unstressed, stressed)
# Vowel + R (and AY + ER, a word-final AH0 + L) are one label in this vocabulary ("car" kɑːɹ, "fire" faɪɚ).
MERGES = [(r"AA\d?", "R", "ɑːɹ", False), (r"AO\d?", "R", "ɔːɹ", False), (r"EH\d?", "R", "ɛɹ", False),
          (r"(IH|IY)\d?", "R", "ɪɹ", False), (r"UH\d?", "R", "ʊɹ", False), (r"AY\d?", r"ER\d?", "aɪɚ", False),
          ("AH0", "L", "əl", True)]


@dataclass(frozen=True)
class Unit:
    """One aligner label and the ARPAbet phones it stands for."""
    ipa: str
    arpabet: tuple


def to_ipa(phone: str) -> str:
    m = re.fullmatch(r"([A-Z]+)([012]?)", phone.upper())
    if m and m[1] in STRESSED:
        return STRESSED[m[1]][m[2] != "0"]
    if not m or m[1] not in BASE:
        raise ValueError(f'"{phone}" is not an ARPAbet phone (CMUdict\'s set: AA AE AH … ZH, vowels with stress 0/1/2)')
    return BASE[m[1]]


def units(phones: list[str]) -> list[Unit]:
    out, i = [], 0
    while i < len(phones):
        a, b = phones[i].upper(), phones[i + 1].upper() if i + 1 < len(phones) else None
        hit = next((ipa for ra, rb, ipa, last in MERGES if b is not None and re.fullmatch(ra, a) and re.fullmatch(rb, b)
                    and (not last or i + 2 == len(phones))), None)
        out.append(Unit(hit, (a, b)) if hit else Unit(to_ipa(a), (a,)))
        i += 2 if hit else 1
    return out


def dict_path() -> Path:
    return Path(os.environ.get("ROSTRUM_CMUDICT") or
                models_dir() / "cmudict-7479086" / "cmudict.dict")


@lru_cache(maxsize=1)
def _dictionary(path: str) -> dict:
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        body = line.split("#", 1)[0].split()
        if len(body) > 1 and not body[0].endswith(")") and body[0] not in out:   # first pronunciation only
            out[body[0]] = body[1:]
    return out


def key(word: str) -> str:
    return re.sub(r"[^\w']", "", word.lower().replace("’", "'")).strip("'_")


def words(text: str, pronounce: dict | None = None, where: str = "lipsync") -> list[tuple[str, list[Unit]]]:
    """Each word of `text` with its labels. A word in neither `pronounce` nor CMUdict is a loud error."""
    own = {key(w): p.split() for w, p in (pronounce or {}).items()}
    path = dict_path()
    if not path.is_file():
        raise RostrumError(codes.MODEL_MISSING, where, "the CMU Pronouncing Dictionary", f"is not at {path}",
                           hint="Set ROSTRUM_CMUDICT to cmudict.dict, or leave out the text to decode freely.")
    cmu, out = _dictionary(str(path)), []
    for w in filter(None, (key(t) for t in text.split())):
        phones = own.get(w) or cmu.get(w)
        if not phones:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'the word "{w}"', "is not in CMUdict",
                               hint=f'Give its sound: pronounce={{"{w}": "R AA1 S T R AH0 M"}} (ARPAbet).')
        try:
            out.append((w, units(phones)))
        except ValueError as e:
            raise RostrumError(codes.BAD_ARGUMENT, where, f'pronounce["{w}"]', str(e)) from e
    return out
