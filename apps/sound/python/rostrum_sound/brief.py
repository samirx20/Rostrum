"""The brief the agent was given, stored on the song (`doc.data["brief"]`, set by the script's brief("...")), and
which of its phrases ask for what.

Round 3E r8 canary: a weak model kept a dull top with "a soft warm piano progression is meant to be dark" while the
brief was only "A 4-bar piano chord progression at 90 bpm"; any excuse passed. A fault may be kept on purpose only
when the brief asks for it, so the words that mean "asks for this" per fault kind are data here, registered into the
shared screen (rostrum_core.mcp.brief_keep: the brief's text, quoting, the keep screen; 2D uses it too):
`register(kind, words)` adds a kind or words (a plugin's own fault too). Warm, soft and mellow are not dark.
"""
from __future__ import annotations

import re

from rostrum_core.mcp.brief_keep import SAYS, WORDS, asks, holds, norm, quoted, register, text, words_for  # noqa: F401  (Sound's callers read them here)

_TIME = re.compile(r"\b\d+(?: \d+)? ?(?:s|sec|secs|second|seconds|bar|bars|beat|beats)\b")    # "at 12 s", "12.5 seconds", "bar 9"
_BAR = re.compile(r"\bbar \d+\b")

register("dull_top", ["dark", "darker", "muffled", "lo-fi", "lofi", "lo fi", "dull", "distant", "far away", "underwater",
                      "under water", "filtered", "low-pass", "low pass", "lowpass", "telephone", "radio",
                      "old record", "vinyl", "gramophone", "through a wall", "next room", "murky", "veiled", "no highs",
                      "smoky"], "a dark or muffled sound")
register("held_tone", ["drone", "drones", "pedal", "pedal tone", "held", "held chord", "held note", "sustained", "static",
                       "one chord", "single chord", "ambient bed", "unchanging", "hum"],
         "a held, unchanging sound")
register("near_mono", ["mono", "monophonic", "vintage", "radio", "telephone", "centred", "centered", "narrow",
                       "old record", "gramophone", "single speaker"], "a mono or narrow sound")
for _k, _what in (("leading_silence", "silence or a late start"), ("dead_air_end", "silence or an early end")):
    register(_k, ["silence", "silent", "pause", "starts at", "start at", "begins at", "comes in at",
                  "ends at", "end at", "stops at", "gap", "breath", _TIME, _BAR], _what)
register("off_tempo", ["rubato", "free time", "free tempo", "tempo change", "tempo changes", "accelerando", "ritardando",
                       "slows down", "speeds up", "out of time"], "free or changing time")
register("clean_ending", ["ends cleanly", "end cleanly", "clean ending", "clean end", "real ending", "hard stop",
                          "stops dead", "not a fade", "no fade", "button ending", "ends on", "end on",
                          "final chord", "final hit", "sting"], "a clean ending")

