"""The brief the agent was given, stored on the song (`doc.data["brief"]`, set by the script's brief("...")), and
which of its phrases ask for what.

Round 3E r8 canary: a weak model kept a dull top with "a soft warm piano progression is meant to be dark" while the
brief was only "A 4-bar piano chord progression at 90 bpm"; any excuse passed. A fault may be kept on purpose only
when the brief asks for it, so the words that mean "asks for this" per fault kind are data here: `register(kind,
words)` adds a kind or words (a plugin's own fault too). A word is a phrase matched whole-word, case- and
punctuation-blind, or a compiled pattern matched on the normalised text. Warm, soft and mellow are not dark.
"""
from __future__ import annotations

import re

_TIME = re.compile(r"\b\d+(?: \d+)? ?(?:s|sec|secs|second|seconds|bar|bars|beat|beats)\b")    # "at 12 s", "12.5 seconds", "bar 9"
_BAR = re.compile(r"\bbar \d+\b")

WORDS: dict[str, list] = {}
SAYS: dict[str, str] = {}       # what a kind's words ask for, in the refusal's own words


def register(kind: str, words, says: str | None = None) -> None:
    """Add the phrases (or compiled patterns) that mean the brief asks for `kind`; `says`: what that is, in plain
    words ("a dark or muffled sound")."""
    WORDS.setdefault(kind, []).extend(words)
    if says:
        SAYS[kind] = says


register("dull_top", ["dark", "darker", "muffled", "lo-fi", "lofi", "lo fi", "dull", "distant", "far away", "underwater",
                      "under water", "filtered", "low-pass", "low pass", "lowpass", "telephone", "radio",
                      "old record", "vinyl", "gramophone", "through a wall", "next room", "murky", "veiled", "no highs",
                      "smoky"], "a dark or muffled sound")
register("held_tone", ["drone", "drones", "pedal", "pedal tone", "held", "held chord", "held note", "sustained", "static",
                       "one chord", "single chord", "ambient bed", "unchanging", "hum"],
         "a held, unchanging sound")
register("near_mono", ["mono", "monophonic", "vintage", "radio", "telephone", "centred", "centered", "narrow",
                       "old record", "gramophone", "single speaker"], "a mono or narrow sound")
register("leading_silence", ["silence", "silent", "pause", "starts at", "start at", "begins at", "comes in at",
                             "ends at", "end at", "stops at", "gap", "breath", _TIME, _BAR], "silence or a late start")
register("off_tempo", ["rubato", "free time", "free tempo", "tempo change", "tempo changes", "accelerando", "ritardando",
                       "slows down", "speeds up", "out of time"], "free or changing time")
register("clean_ending", ["ends cleanly", "end cleanly", "clean ending", "clean end", "real ending", "hard stop",
                          "stops dead", "not a fade", "no fade", "button ending", "ends on", "end on",
                          "final chord", "final hit", "sting"], "a clean ending")

register("fade_ending", ["fade out", "fades out", "fade-out", "fading out", "fade away", "fades away", "fade to silence",
                         "fades to silence", "fade to black"], "a fade-out")
register("hard_stop", ["hard stop", "stops dead", "dead stop", "cut off", "cuts off", "abrupt end", "abrupt ending",
                       "ends abruptly", "hard cut", "cut to silence", "stops mid", "mid note", "mid-note"], "a hard stop")
register("loop", ["loop", "loops", "loopable", "looping", "seamless loop", "loops seamlessly"], "a loop")
register("thin_ending", [re.compile(r"\b(?:alone|solo|by itself|on its own)\b.*\bend(?:s|ing)?\b"),
                         re.compile(r"\bend(?:s|ing)?\b.*\b(?:alone|solo|by itself|on its own)\b")],
         "an ending on fewer parts (\"the piano alone ends it\")")
register("open_ending", ["unresolved", "open ending", "open end", "ends open", "left hanging", "hangs", "unfinished",
                         "question mark", "ends on a question"], "an open, unresolved ending")
# bad_ending (listen/end_check.py: one fault for every way an ending fails) may be kept only when the brief asks for that
# ending (round sound-ascent: a delivery fade was kept with "decays to a quiet ending", which asks for a decay, not a fade)
register("bad_ending", [*WORDS["fade_ending"], *WORDS["open_ending"], *WORDS["hard_stop"], *WORDS["loop"]],
         "that ending (a fade-out, a hard stop, a loop or an open end)")


def norm(text: str) -> str:
    """Lower case, every run of punctuation and space one space ("Lo-Fi, dark!" -> "lo fi dark")."""
    return " ".join(re.sub(r"[^0-9a-z]+", " ", (text or "").lower()).split())


def text(data: dict | None) -> str:
    """The stored brief, "" when none."""
    b = (data or {}).get("brief")
    return b.strip() if isinstance(b, str) else ""


NOT = {"no", "not", "without", "never", "nor", "avoid", "avoiding", "t", "zero", "non", "neither", "instead"}   # "don't" -> "don t"
NOT_REACH = 3        # a negating word up to this many words before a phrase undoes it: "no build", "without any big build"


def _has(phrase: str, word) -> bool:
    """Whether the normalised `phrase` holds `word` (a phrase, whole words) or matches its pattern. A phrase negated
    just before it ("no build", "never builds") is not asked: a7's "(no build, no drop)" read as asking for a build."""
    if isinstance(word, re.Pattern):
        return bool(word.search(phrase))
    w = norm(word)
    if not w:
        return False
    said, ws = phrase.split(), w.split()
    for i in range(len(said) - len(ws) + 1):
        if said[i:i + len(ws)] == ws and not NOT & set(said[max(0, i - NOT_REACH):i]):
            return True
    return False


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
