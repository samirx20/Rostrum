"""A voice-over's lines as 2D shows them on the Sound row (UX_SPEC 3.28; docs/PLAN.md › Sound in 2D (3)): each spoken
line's words, where it starts and ends in seconds, read from the song RostrumSound already gave us whole
(soundtrack.read), through Sound's own readers (voice_lines, doc.times): never a file path of ours. A line whose
take is not made yet runs to the next line (or 2 s). No Qt.
"""
from __future__ import annotations

FALLBACK = 2.0               # seconds shown for a line that has no take yet


def lines(folder, root: dict) -> list[dict]:
    """[{t, end, text, track}] in time order; [] for a song without voice lines."""
    from rostrum_sound import voice_lines
    from rostrum_sound.doc import markers, times
    found = voice_lines.lines(root)
    if not found:
        return []
    out = []
    with markers.project(folder):
        for track, ln in found:
            t = times.seconds(ln["at"], root, f"line {ln['id']}")
            take = voice_lines.take_of(track, ln)
            out.append({"t": round(t, 3), "end": round(t + take.seconds, 3) if take else None, "text": ln["text"],
                        "track": track.get("name") or track["id"]})
    out.sort(key=lambda r: r["t"])
    for a, b in zip(out, out[1:] + [None]):
        if a["end"] is None:
            a["end"] = b["t"] if b else a["t"] + FALLBACK
    return out
