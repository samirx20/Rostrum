"""A kept fault must be one the brief asks for, quoted from it.

Round 3E r8 canary: Haiku shipped 4 songs keeping a dull top with "a soft warm piano progression is meant to be dark"
while the brief was "A 4-bar piano chord progression at 90 bpm"; the shared rule took any reason. So every `keep`
entry, for any fault, now needs the brief stored on the song (brief("...") in the script) and a reason that quotes it
(a quoted phrase of the brief, or 3 or more of its words in a row); where the fault's kind has words that mean the
brief asks for it (../brief.py), the quoted part must hold one ("a 4-bar piano progression" cannot keep a dull top).
A refused entry is set aside before the shared gate (rostrum_core.mcp.faults.deliver), which then refuses as usual,
and the fault's fix says why in one sentence with the next step. Runs after asked_keep.screen (the moment the brief
asked for has its own, stricter rule)."""
from __future__ import annotations

import re

from .. import brief

NO_BRIEF = ("no brief stored; put the brief's own words in the script with brief(\"...\") (or edit_document doc.set "
            "brief) and quote the part that asks for this")


def kind(fault_id: str) -> str:
    """The fault's kind from its id ("weak_hit@31.5" -> weak_hit, "duck:voice" -> duck)."""
    return re.split(r"[:@]", fault_id, maxsplit=1)[0]


def why_not(fault_id: str, reason: str, data: dict | None) -> str | None:
    """Why `reason` may not keep this fault (one plain sentence), or None when it may."""
    if not brief.text(data):
        return NO_BRIEF
    spans, k = brief.quoted(reason, data), kind(fault_id)
    if not spans:
        return ("the reason does not quote the brief; put the brief's own words that ask for this in quotes "
                f"(the brief stored with brief(\"...\") is: \"{brief.text(data)[:160]}\")")
    if any(brief.holds(k, s) for s in spans):
        return None
    return (f"the brief (stored with brief(\"...\")) never asks for {brief.SAYS.get(k, 'this')} in the words quoted "
            f"(\"{k}\" needs one of: {brief.words_for(k)})")


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
