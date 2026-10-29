"""The whole song's mastering decisions (the engine's `decisions`: the program's loudness, the gain to the target, how
far it is held under it), kept per song so a heard stretch is mastered as the song is (hear.py, the engine's
`masterAs`): the stretch then renders on its own in a fraction of a second, sample for sample what the full render has
there. Kept in the cache (`sound/auditions/master/`), one small file per song, with the key of the song they were
worked out on: when the song has changed since, they are what the song last measured, and the reply says so.

    song_of(folder, item)              # which song: its project folder and item
    key(schedule)                      # the song's key (its compiled schedule)
    remember(song, key, reply)         # a reply's decisions, for that song as it was
    given(song, key) -> (decisions | None, fresh)
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import settings


def _file(song: str) -> Path:
    return settings.cache_dir() / "sound" / "auditions" / "master" / (hashlib.sha256(song.encode()).hexdigest()[:24] + ".json")


def song_of(folder, item: str) -> str:
    return f"{str(Path(folder or '.').resolve()).lower()}|{item}"


def key(schedule: dict) -> str:
    return hashlib.sha256(json.dumps(schedule, sort_keys=True, default=str).encode()).hexdigest()[:24]


def remember(song: str, k: str, reply: dict) -> None:
    """The reply's decisions (a whole render's, or a stretch cut from the whole song) kept for `song` as keyed `k`."""
    d = reply.get("decisions")
    if not d or reply.get("windowed"):
        return
    f = _file(song)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"key": k, "decisions": d}), encoding="utf-8")


def given(song: str, k: str) -> tuple[dict | None, bool]:
    """The song's last decisions and whether they were worked out on the song as it is now (`k`)."""
    f = _file(song)
    try:
        got = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, False
    return got.get("decisions"), got.get("key") == k
