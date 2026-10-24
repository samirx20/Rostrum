"""The project's voice lines as Lip sync lists them (UX_SPEC 3.23 > Lip sync): read from RostrumSound's items through
the project service and Sound's read-only API (rostrum_sound.soundtrack.read, voice_lines), never a file path a person
types. One source of truth: the words, the time and the take are Sound's. Shared by 2D and 3D. No Qt.

    lines(folder) -> [{"id": "voice/hello", "item", "line", "text", "at": s, "file": take wav or "", "english": bool}]
"""
from __future__ import annotations

from .. import project


def lines(folder) -> list[dict]:
    """Every voice line of every Sound item, in item then document order. `at`: where the line starts in the song (a
    song plays from the scene's 0 s); `file`: its made take ("" = not made yet: RostrumSound's Make voice)."""
    if not folder:
        return []
    from rostrum_sound import soundtrack, voice_lines
    from rostrum_sound.doc import times
    out = []
    for item in project.items(folder, "sound"):
        root = soundtrack.read(folder, item["id"])
        for track, line in voice_lines.lines(root):
            take = voice_lines.take_of(track, line)
            out.append({"id": f'{item["id"]}/{line["id"]}', "item": item["id"], "line": line["id"], "text": line["text"],
                        "at": round(times.seconds(line["at"], root, f"line {line['id']}"), 4),
                        "file": take.file if take else "", "song": item.get("name", item["id"]),
                        "english": track.get("language", "auto") in ("auto", "english")})
    return out


def heard(line: dict) -> bool:
    """Its phones are in the cache already (Apply is quick); else Apply listens first (the phone model, a while)."""
    from . import phonemes
    k = phonemes.key(line["file"], 0.0, None, line["text"] if line["english"] else None, "english", None)
    return phonemes.CACHE.get("lipsync", k) is not None
