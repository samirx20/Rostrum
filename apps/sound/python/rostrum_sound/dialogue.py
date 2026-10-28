"""Dialogue tracks and the ducks under them, worked out where the document becomes the engine's schedule (compile.py).

A track is dialogue when it says so (`role: "dialogue"`: a voice-over file, an interview, any speech) or when it is a
voice track (it speaks lines). A duck stores only what was written: an empty `under` means "every dialogue track",
and a duck with no `voice` written dips for whole lines exactly when every track it is under is dialogue (a
short attack and release with a 0.3 s hold across the gaps between words), else it pumps per hit. Both are resolved
at each compile, so a dialogue track added later is picked up and the stored document stays as it was written.

    vo = track("vo", role="dialogue"); vo.clip("media/vo.wav", at=0)
    music.duck()                       # under every dialogue track, whole lines
"""
from __future__ import annotations

from rostrum_core import RostrumError, codes

DIALOGUE = "dialogue"
VOICE_HOLD = 0.3        # seconds the dip stays down across the gaps between words (what duck.add always gave a voice)
FIX = ('mark the speech track as dialogue (script: track("vo", role="dialogue"); edit_document: track.set '
       '{"role": "dialogue"}), or name the tracks to duck under: duck(under=["vo"])')


def is_dialogue(track: dict | None) -> bool:
    return bool(track) and (track.get("role") == DIALOGUE or track.get("instrument") == "voice")


def dialogue_ids(tracks: list[dict], but: str | None = None) -> list[str]:
    return [t["id"] for t in tracks if is_dialogue(t) and t["id"] != but]


def under_of(duck: dict, owner: str, tracks: list[dict]) -> list[str]:
    """The tracks the duck dips under: as written, or every dialogue track but its own when `under` is empty."""
    return list(duck.get("under") or ()) or dialogue_ids(tracks, but=owner)


def resolve(duck: dict, owner: str, tracks: list[dict], where: str) -> dict:
    """The duck as the engine takes it: `under`, `voice` and `hold` worked out; the rest as written. An empty `under`
    with no dialogue track is a loud error naming the fix."""
    under = under_of(duck, owner, tracks)
    if not under:
        raise RostrumError(codes.BAD_ARGUMENT, where, "duck with no `under`",
                           "dips under every dialogue track, and this song has none", hint="Fix: " + FIX + ".")
    by_id = {t["id"]: t for t in tracks}
    voice = duck["voice"] if "voice" in duck else all(is_dialogue(by_id.get(u)) for u in under)
    hold = duck["hold"] if "hold" in duck else (VOICE_HOLD if voice else 0.0)
    return {**duck, "under": under, "voice": bool(voice), "hold": hold}
