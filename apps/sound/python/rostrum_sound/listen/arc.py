"""arc: a piece the brief asks to begin quiet or end quiet, measured against its own loudest moment.

Round sound-tighten, brief 4 (Ascent: "begins quiet ... builds ... the climax at 38 s ... settles and decays to a quiet
ending"): both Rostrum runs opened only 15–16 LU under their climax and one ended 12 LU under it; the rival opened 29 LU
under and ended 35 LU under. Both judges picked the rival for exactly that arc, and no check had read it: the climax
checks read the downbeat, the hold and the bloom, never how far the piece travels to get there. So when the brief asks
for a quiet start (brief.asks "quiet_start") the first OPEN_S of sound is read against the loudest 3 s, and when it asks
for a quiet ending ("quiet_ending") the last END_S. A loudness target does not undo this: the master turns the whole
file up or down, so the distance between the opening and the climax is the script's.

    fault(doc, wav) -> [shared fault]   (ids loud_opening, loud_ending)
"""
from __future__ import annotations

import re

from rostrum_core.mcp import faults as shared

from .. import brief
from .bs1770 import integrated
from .core import load, num
from .lead_in import first_sound_s
from .loudness import loudest

OPEN_S = 4.0         # the opening: the first 4 s from the first sound
END_S = 2.0          # the ending: the file's last 2 s
UNDER_LU = 20.0      # a quiet opening or ending sits at least this far under the loudest 3 s (rival 29 / 35; ours 15 / 12)
QUIET_LUFS = -70.0

_START = re.compile(r"\b(?:begin|begins|beginning|start|starts|starting|open|opens|opening|intro)\b(?: \w+){0,3} "
                    r"(?:quiet|quietly|soft|softly|hushed|gently|gentle|pianissimo|delicate|delicately|barely|whisper)\b")
_END = re.compile(r"\b(?:quiet|quietly|soft|softly|hushed|gentle|gently|pianissimo|whisper|nothing|silence)\b(?: \w+){0,2} "
                  r"(?:end|ending|close|finish|outro)\b|\b(?:ends?|ending|finish|finishes|outro|close|closes)\b(?: \w+){0,3} "
                  r"(?:quiet|quietly|soft|softly|gently|silence|nothing|whisper)\b")
brief.register("quiet_start", ["from silence", "out of silence", "from nothing", "out of nothing", "pianissimo", "barely audible",
                               "quiet intro", "soft intro", _START], "a quiet start")
brief.register("quiet_ending", ["dies away", "die away", "fades to nothing", "fade to nothing", "to silence", "into silence",
                                "winds down", "trails off", _END], "a quiet ending")
# what keeps a loud opening or ending: the brief asking for one (never the quiet words above)
brief.register("loud_opening", ["loud start", "starts loud", "opens loud", "starts big", "opens big", "in your face",
                                "cold open", "starts with a bang", "starts on a hit"], "a loud start")
brief.register("loud_ending", ["loud ending", "ends loud", "ends big", "big finish", "big ending", "ends on a hit",
                               "button ending", "sting"], "a loud ending")

OPEN_FIX = ("play the opening softer and thinner: velocity moves recorded instruments a long way (built-in strings at "
            "0.3 sit about 16 dB under 1.0, at 0.2 about 22 dB), so start the first parts at velocity 0.2–0.35 or under a "
            "track.dynamics lane that rises across the build (track.dynamics([(0, 0.3), (\"#climax\", 1.0)])), start with "
            "one or two parts and add the rest on the way up, and let the loudest moment be loud because everyone plays "
            "(tutti, sustained brass and strings), not because of higher peaks; the opening must still speak at once "
            "(a soft note that starts at once, not silence)")
END_FIX = ("let the piece fall away after its peak: parts drop out one by one, a track.dynamics lane falling to 0.2–0.3, "
           "the last chord soft (velocity 0.2–0.35) and short of the file's end so its tail dies away inside the file "
           "(not a delivery fade: Ring out on, the song's length 1–2 s after the last note)")


def measure(wav) -> dict | None:
    """{peak_lufs, peak_from_s, opening_lufs, opening_under_lu, ending_lufs, ending_under_lu}; None when the file is
    too short to have an opening, a peak and an ending apart (under 3 × OPEN_S)."""
    y, sr = load(wav)
    n = len(y) / sr
    if n < 3 * OPEN_S:
        return None
    top = loudest(y, sr)["short_term_3s"]
    t0 = first_sound_s(y, sr) or 0.0
    cut = lambda a, b: max(QUIET_LUFS, integrated(y[int(a * sr):int(b * sr)], sr))   # noqa: E731
    op, end = cut(t0, t0 + OPEN_S), cut(n - END_S, n)
    return {"peak_lufs": top["lufs"], "peak_from_s": top["from_s"], "opening_lufs": num(op, 1),
            "opening_under_lu": num(top["lufs"] - op, 1), "ending_lufs": num(end, 1), "ending_under_lu": num(top["lufs"] - end, 1)}


def fault(doc, wav) -> list[dict]:
    """The arc faults the brief stored on `doc` asks for (none without a brief that asks)."""
    data = getattr(doc, "data", None) or {}
    start, finish = brief.asks(data, "quiet_start"), brief.asks(data, "quiet_ending")
    if not (start or finish) or not wav:
        return []
    m = measure(wav)
    if not m:
        return []
    out, top = [], f"the loudest 3 s ({m['peak_lufs']:g} LUFS from {m['peak_from_s']:g} s)"
    if start and m["opening_under_lu"] < UNDER_LU:
        out.append(shared.fault("loud_opening", f"the opening is not quiet, and the brief asks for it (\"{start}\"): its first "
                                f"{OPEN_S:g} s sit {m['opening_under_lu']:g} LU under {top}; a quiet start sits {UNDER_LU:g} LU "
                                f"or more under it", OPEN_FIX, "the opening"))
    if finish and m["ending_under_lu"] < UNDER_LU:
        out.append(shared.fault("loud_ending", f"the ending is not quiet, and the brief asks for it (\"{finish}\"): its last "
                                f"{END_S:g} s sit {m['ending_under_lu']:g} LU under {top}; a quiet ending sits {UNDER_LU:g} LU "
                                f"or more under it", END_FIX, "the end"))
    return out
