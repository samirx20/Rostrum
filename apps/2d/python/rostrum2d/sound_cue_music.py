"""The musical answers "Add a sound here" offers first (apps/sound/PURPOSE.md: instruments and soundtrack, no effects):
a note on one of the song's own instruments, or a hit on its drum kit, struck on the layer's moment. A song with no
instrument yet gets Sound's own motion answers (a struck bell note, a kick and cymbal hit: rostrum_sound.motion.score,
one source of truth for how they are played). A choice is a word, not a file: "note:<track>" / "hit:<track>".

    rows(snd)                            # [{path: "note:piano", about: "A note on Piano", where: "Your song"} …]
    calls(snd, "note:piano", "#Logo · sound")   # Sound operations that strike it there (a track first when needed)
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

DRUMS, SILENT = {"kit", "kitSfz"}, {"none", "voice", None}


def is_music(choice: str) -> bool:
    return choice.partition(":")[0] in ("note", "hit") and ":" in choice


def _tracks(snd) -> list[dict]:
    return [t for t in snd.data.get("tracks", []) if t.get("instrument") not in SILENT]


def rows(snd) -> list[dict]:
    """The song's instruments, each a note (or a hit for a drum kit) on the moment; else Sound's bell note and hit."""
    from rostrum_sound.motion import score
    out = [{"path": f'{"hit" if t["instrument"] in DRUMS else "note"}:{t["id"]}', "where": "Your song",
            "about": f'A {"hit" if t["instrument"] in DRUMS else "note"} on {t.get("name") or t["id"]}'}
           for t in (_tracks(snd) if snd else [])]
    if not out:
        out = [{"path": f"{a}:{score.TRACKS[a][0]}", "about": score.SAYS[a][0].upper() + score.SAYS[a][1:],
                "where": "New instrument"} for a in ("note", "hit")]
    return out


def calls(snd, choice: str, when: str) -> list[dict]:
    """Sound operations striking `choice` at `when` (a marker reference): score.parts places it, in the song's key."""
    from rostrum_sound.doc import keys
    from rostrum_sound.motion import score
    answer, _, track = choice.partition(":")
    have = {t["id"]: t for t in snd.data.get("tracks", [])}
    out = []
    if track not in have:
        plays = next((p for t, p in score.TRACKS.values() if t == track), None)
        if plays is None:
            raise RostrumError(codes.NOT_FOUND, "sound.cue", f'track "{track}"', "is not in the song",
                               hint="Pick one of the song's instruments (inspect_sounds).")
        (kind, name), = plays.items()
        out.append({"op": "track.add", "args": {"id": track, "name": track.replace("motion_", "").title(),
                                                  "instrument": kind, kind: name}})
    key = keys.key_at(snd.data, 0.0) or "C major"
    placed = score.parts([({"at": when, "hardness": 0.6, "rise_s": 0.0}, answer)], key)
    return out + [{"op": f"{call}.add", "target": [track], "args": {**f, "at": when}} for _, call, f in placed]
