"""The whole song's mastering decisions (the engine's `decisions`: the program's loudness, the gain to the target, how
far it is held under it), kept per song so a heard stretch is mastered as the song is (hear.py, the engine's
`masterAs`): the stretch then renders on its own in a fraction of a second, sample for sample what the full render has
there. Kept in the cache (`sound/auditions/master/`), one small file per song, with the key of the song they were
worked out on: when the song has changed since, they are what the song last measured, and the reply says so; then the
song is measured again at once in the background (`refresh`: one full-song pass, about two seconds, which also puts the
changed track into the render cache whole), and the next stretch waits for it, so it is exact again.

    song_of(folder, item)              # which song: its project folder and item
    key(schedule)                      # the song's key (its compiled schedule)
    remember(song, key, reply)         # a reply's decisions, for that song as it was
    given(song, key) -> (decisions | None, fresh)   # waits for a refresh of the song still running
    refresh(engine, song, key, schedule)               # measure the song as it is now, in the background
"""
from __future__ import annotations

import hashlib
import json
import threading
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


_running: dict[str, tuple[str, threading.Thread]] = {}       # song -> (key being measured, its thread)
_guard = threading.Lock()


def refresh(engine, song: str, k: str, schedule: dict) -> None:
    """The song (`schedule`, keyed `k`) measured whole in the background: its decisions kept when done. A refresh of the
    same song as it is is not started twice; a failure leaves the older decisions (the next listen says so again)."""
    with _guard:
        if song in _running and _running[song][0] == k and _running[song][1].is_alive():
            return
        out = _file(song).with_name(f"refresh-{k}.wav")

        def work():
            try:
                out.parent.mkdir(parents=True, exist_ok=True)
                remember(song, k, engine.request("render", schedule=schedule, out=str(out), stems=[], **{"from": 0.0, "to": 0.1, "inSong": True}))
            except Exception:                    # noqa: BLE001 — the older decisions stay; the next listen says so
                pass
            finally:
                for p in (out, out.with_suffix(".levels.json")):
                    p.unlink(missing_ok=True)

        t = threading.Thread(target=work, name="master-refresh", daemon=True)
        _running[song] = (k, t)
        t.start()


def given(song: str, k: str) -> tuple[dict | None, bool]:
    """The song's last decisions and whether they were worked out on the song as it is now (`k`); a refresh of this song
    still running is waited for first."""
    with _guard:
        running = _running.get(song)
    if running and running[1].is_alive():
        running[1].join(timeout=30)
    f = _file(song)
    try:
        got = json.loads(f.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None, False
    return got.get("decisions"), got.get("key") == k
