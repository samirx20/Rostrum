"""A kept fault must be one the brief asks for, quoted from it (the screen every app runs before faults.deliver).

Round 3E r8 canary: Haiku shipped 4 songs keeping a dull top with "a soft warm piano progression is meant to be dark"
while the brief was "A 4-bar piano chord progression at 90 bpm"; the shared rule took any reason. So every `keep`
entry, for any fault, needs the brief stored on the document (`doc.data["brief"]`, set by the script's brief("..."))
and a reason that quotes it (a quoted phrase of the brief, or 3 or more of its words in a row). Where a fault's kind has
words that mean the brief asks for it (`register(kind, words)`: Sound registers dull_top's "dark, muffled, ..."), the
quoted part must hold one ("a 4-bar piano progression" cannot keep a dull top). A refused entry is set aside before
faults.deliver, which then refuses as usual, and the fault's fix says why in one sentence with the next step.

A word is a phrase matched whole-word, case- and punctuation-blind, or a compiled pattern matched on the normalised text.
"""
from __future__ import annotations

import re

WORDS: dict[str, list] = {}
SAYS: dict[str, str] = {}       # what a kind's words ask for, in the refusal's own words

NO_BRIEF = ("no brief stored; put the brief's own words at the top of the script with brief(\"...\") "
            "and quote the part that asks for this")


def register(kind: str, words, says: str | None = None) -> None:
    """Add the phrases (or compiled patterns) that mean the brief asks for `kind`; `says`: what that is, in plain
    words ("a dark or muffled sound")."""
    WORDS.setdefault(kind, []).extend(words)
    if says:
        SAYS[kind] = says


def norm(text: str) -> str:
    """Lower case, every run of punctuation and space one space ("Lo-Fi, dark!" -> "lo fi dark")."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", (text or "").lower()).split())


def text(data: dict | None) -> str:
    """The stored brief, "" when none."""
    b = (data or {}).get("brief")
    return b.strip() if isinstance(b, str) else ""


def _has(phrase: str, word) -> bool:
    """Whether the normalised `phrase` holds `word` (a phrase, whole words) or matches its pattern."""
    if isinstance(word, re.Pattern):
        return bool(word.search(phrase))
    w = norm(word)
    return bool(w) and f" {w} " in f" {phrase} "


def holds(kind: str, phrase: str) -> bool:
    """Whether `phrase` holds one of the words that ask for `kind` (True when the kind has no word table)."""
    words = WORDS.get(kind)
    return words is None or any(_has(norm(phrase), w) for w in words)


def asks(data: dict | None, kind: str) -> str | None:
    """The brief's phrase (one clause, as written) that asks for `kind`, or None (no brief, no table, no such words)."""
    if kind not in WORDS:
        return None
    for clause in re.split(r"[.;:,!?\n()]+|\s[-–—]\s", text(data)):
        if clause.strip() and holds(kind, clause):
            return clause.strip()
    return None


def words_for(kind: str, n: int = 6) -> str:
    """The first few words that ask for `kind`, for a refusal ("dark, muffled, lo-fi ...")."""
    plain = [w for w in WORDS.get(kind, []) if isinstance(w, str)]
    return ", ".join(plain[:n]) + (" ..." if len(plain) > n else "")


def quoted(reason: str, data: dict | None) -> list[str]:
    """The parts of `reason` that are the brief's own words (normalised): each quoted phrase found in the brief, and
    each run of 3 or more consecutive brief words. [] when there is no brief or nothing quotes it."""
    brief = norm(text(data))
    if not brief:
        return []
    marks = re.findall(r'"([^"]+)"|“([^”]+)”|\'([^\']{3,})\'', reason or "")
    spans = [q for q in (norm(part) for groups in marks for part in groups if part) if q and f" {q} " in f" {brief} "]
    words, said = brief.split(), norm(reason).split()
    i = 0
    while i < len(said):                     # the longest run of brief words starting here
        best = 0
        for j in range(len(words)):
            k = 0
            while i + k < len(said) and j + k < len(words) and said[i + k] == words[j + k]:
                k += 1
            best = max(best, k)
        if best >= 3:
            spans.append(" ".join(said[i:i + best]))
            i += best
        else:
            i += 1
    return spans


def kind(fault_id: str) -> str:
    """The fault's kind from its id ("weak_hit@31.5" -> weak_hit, "duck:voice" -> duck)."""
    return re.split(r"[:@]", fault_id, maxsplit=1)[0]


def why_not(fault_id: str, reason: str, data: dict | None) -> str | None:
    """Why `reason` may not keep this fault (one plain sentence), or None when it may."""
    if not text(data):
        return NO_BRIEF
    spans, k = quoted(reason, data), kind(fault_id)
    if not spans:
        return ("the reason does not quote the brief; put the brief's own words that ask for this in quotes "
                f"(the brief stored with brief(\"...\") is: \"{text(data)[:160]}\")")
    if any(holds(k, s) for s in spans):
        return None
    return (f"the brief (stored with brief(\"...\")) never asks for {SAYS.get(k, 'this')} in the words quoted "
            f"(\"{k}\" needs one of: {words_for(k)})")


def screen(found: list[dict], keep: dict | None, data: dict | None) -> dict:
    """`keep` without the entries the brief does not back; each refused one says why in its fault's fix."""
    keep = dict(keep or {})
    for f in found:
        if f["id"] not in keep:
            continue
        if (why := why_not(f["id"], str(keep[f["id"]]), data)) is not None:
            del keep[f["id"]]
            f["fix"] = f"keep refused: {why}; fix it instead: {f['fix']}"
    return keep
