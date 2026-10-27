"""How long a spoken line will take, from its words alone, before it is made (so an agent can fit it to the music).

`estimate(text, language)` answers `{"seconds", "low", "high", "basis"}`. It counts syllables (letters in Latin
scripts; one per character in Chinese, one per kana in Japanese, one per syllable block in Korean), adds a pause for
each comma, colon, semicolon and sentence end, and multiplies by the speaking rate. The rates were measured on the
real voice model (Qwen3-TTS, 17 takes in English, German, Chinese and Japanese; VOICE.md "How long a line takes"):
the same words come out 10-25 % faster or slower from one reading (seed) to the next, so the range is wide on
purpose. A made take is exact: use its `seconds` (`voice_lines.timing`).
"""
from __future__ import annotations

import re

# seconds per syllable and per pause, measured (VOICE.md); a style such as "slow" or "excited" moves the pace by as
# much as the range, so it is not modelled.
PER_SYLLABLE = {"latin": 0.245, "chinese": 0.215, "japanese": 0.135, "korean": 0.2}
PER_COMMA = 0.15
PER_END = 0.45
START = 0.1            # the breath before the first word and the tail after the last
SPREAD = 0.22          # the range either side, as a share of the estimate (1 sigma of the measured takes, about)
MIN_SPREAD = 0.3       # seconds

_CJK = re.compile(r"[一-鿿]")
_KANA = re.compile(r"[぀-ヿ]")
_HANGUL = re.compile(r"[가-힣]")
_SMALL_KANA = set("ゃゅょぁぃぅぇぉゎャュョァィゥェォヮー")
_VOWELS = re.compile(r"[aeiouyäöüéèàáíóúâêîôûæœ]+")
_NUMBER = re.compile(r"\d+")


def _syllables(word: str) -> int:
    w = word.lower()
    n = len(_VOWELS.findall(w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n) if any(c.isalpha() for c in w) else 0


def _latin(text: str) -> int:
    total = 0
    for part in text.split():
        digits = _NUMBER.findall(part)
        total += sum(max(1, (len(d) + 1) // 2) + 1 for d in digits)        # "20" is two or three syllables
        total += _syllables(_NUMBER.sub(" ", part).strip("$%€£"))
    return total


def estimate(text: str, language: str = "auto") -> dict:
    """{"seconds", "low", "high", "basis"} for the words (`basis` says which rate was used)."""
    cjk, kana = len(_CJK.findall(text)), len([c for c in _KANA.findall(text) if c not in _SMALL_KANA])
    hangul = len(_HANGUL.findall(text))
    script = "japanese" if kana else "chinese" if cjk else "korean" if hangul else "latin"
    syl = {"chinese": cjk, "japanese": kana + cjk * 2, "korean": hangul, "latin": _latin(text)}[script]
    commas = len(re.findall(r"[,;:，；：、—–]|\s-\s", text))
    ends = max(1, len(re.findall(r"[.!?…。！？]+", text)))
    sec = START + syl * PER_SYLLABLE[script] + commas * PER_COMMA + (ends - 1) * PER_END
    pad = max(MIN_SPREAD, SPREAD * sec)
    return {"seconds": round(sec, 1), "low": round(max(0.2, sec - pad), 1), "high": round(sec + pad, 1), "basis": script}


def said(e: dict) -> str:
    """The estimate in words: "about 3.2 s (2.5-3.9)"."""
    return f"about {e['seconds']:.1f} s ({e['low']:.1f}-{e['high']:.1f})"
