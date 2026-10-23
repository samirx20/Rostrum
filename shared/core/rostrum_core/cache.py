"""The shared cache (project-service contract § 5): one folder for the whole machine, an entry per key.

A key is a fingerprint of the job kind, the engine and its version, the content of every input and the settings,
so a new engine version never serves an old result. An entry is a folder `<root>/<kind>/<key>/` with the job's
files and an `entry.json` (what made it, when, size, how long). It is made under a temporary name and renamed
when complete: a failed job leaves nothing. Over the cap, the least recently used entries go first; one used in
the last 15 minutes is never removed.

    from rostrum_core.cache import CACHE, cache_key
    k = cache_key("ai.voice", "qwentts@1", [text], {"voice": "ryan"})
    folder = CACHE.get("voice", k) or CACHE.put("voice", k, lambda tmp: make_take(tmp / "take.wav"))

A single cached file (an app's own capped folder: a mix, a sound track, a picture) is made with `put_file`, the same
way: each writer writes its own uniquely named temporary file and moves it into place whole, so two runs of one
project at once both succeed and a reader never sees half a file.

    wav = put_file(folder / f"{key}.wav", lambda tmp: engine.request("render", out=str(tmp)), "soundtrack")
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path
from typing import Callable

from .errors import RostrumError, codes

GB = 1 << 30
DEFAULT_CAP = 20 * GB
KEEP_RECENT_S = 15 * 60
ENTRY = "entry.json"


def cache_key(kind: str, engine: str, inputs=(), settings: dict | None = None) -> str:
    """SHA-256 of the recipe. `engine` names the engine and its version ("rostrum-track@3"); `inputs` are content
    hashes (or the content itself, if small: text, a stroke's JSON); `settings` are written in a fixed order."""
    if "@" not in engine:
        raise ValueError(f"cache_key: engine {engine!r} must carry its version, e.g. 'rostrum-track@3'")
    recipe = {"kind": kind, "engine": engine, "inputs": list(inputs), "settings": settings or {}}
    return hashlib.sha256(json.dumps(recipe, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def file_hash(path) -> str:
    """The content hash of a file, for a key's inputs."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def default_root() -> Path:
    if os.environ.get("ROSTRUM_CACHE_DIR"):
        return Path(os.environ["ROSTRUM_CACHE_DIR"])
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Caches" / "Rostrum"
    return Path.home() / ".rostrum" / "cache"


def _size(folder: Path) -> int:
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file())


WRITING = ".writing"          # the temporary files of `put_file`, kept apart so a trim's glob never sees them


LEVELS = ".levels.json"       # the strips' live meters the engine writes beside every mix (read by the player)


def used_at(out) -> float:
    """When a cached file was last used: its own time or its sidecar's (a hit renews the sidecar, see put_file)."""
    out = Path(out)
    times = [p.stat().st_mtime for p in (out, out.with_suffix(LEVELS)) if p.is_file()]
    return max(times, default=0.0)


def put_file(out, make: Callable[[Path], object], where: str = "cache", beside: tuple[str, ...] = ()) -> Path:
    """The cached file `out`, made by `make(tmp)` if missing. `tmp` is unique to this writer (same suffix as `out`)
    in `<folder>/.writing/`; it moves into place only when written. Two writers of one key both succeed (the
    first one stands); `make` raising, or writing nothing, is loud and leaves nothing behind. A hit renews the time.
    `beside`: the files `make` writes next to `tmp` that belong to `out` (a mix's `.levels.json`: keyed to the mix's
    size and time, so it moves with it and the mix itself is never touched again). A file missing is loud too, and an
    older entry made without them is made again."""
    out = Path(out)
    sides = lambda p: [(p.with_suffix(x)) for x in beside]  # noqa: E731
    if out.is_file() and all(q.is_file() for q in sides(out)):
        try:
            os.utime(sides(out)[0] if beside else out)      # the newest used stays when the folder is trimmed
        except OSError:
            pass                                # open in a player: still a hit
        return out
    tmp = out.parent / WRITING / f"{out.stem}-{os.getpid()}-{uuid.uuid4().hex[:8]}{out.suffix}"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    try:
        make(tmp)
        if not tmp.is_file() or tmp.stat().st_size == 0:
            raise RostrumError(codes.RENDER_FAILED, where, out.name, f"the job answered but wrote no file at {tmp}")
        for q in sides(tmp):
            if not q.is_file():
                raise RostrumError(codes.RENDER_FAILED, where, out.name, f"the job wrote no {q.name[len(tmp.stem):]} beside {tmp}")
        try:
            for q, dest in zip(sides(tmp), sides(out)):
                os.replace(q, dest)             # before the file itself: whoever sees the mix finds its meters
            os.replace(tmp, out)
        except OSError:
            if not out.is_file():               # not "another writer won and a reader holds it open": a real failure
                raise
    finally:
        tmp.unlink(missing_ok=True)
        for q in sides(tmp):
            q.unlink(missing_ok=True)
    return out


class Cache:
    def __init__(self, root=None, cap: int | None = None, clock=time.time):
        self.root = Path(root) if root else default_root()
        self.cap = cap if cap is not None else int(float(os.environ.get("ROSTRUM_CACHE_CAP_GB", 20)) * GB)
        self.clock = clock

    def path(self, kind: str, key: str) -> Path:
        if not kind or "/" in kind or "\\" in kind or kind.startswith("."):
            raise ValueError(f"cache: bad kind {kind!r}")
        return self.root / kind / key

    def get(self, kind: str, key: str) -> Path | None:
        """The entry's folder, or None. A hit counts as a use (it moves to the back of the clean-up line)."""
        folder = self.path(kind, key)
        meta = folder / ENTRY
        if not meta.is_file():
            return None
        os.utime(meta, (self.clock(), self.clock()))
        return folder

    def put(self, kind: str, key: str, make: Callable[[Path], object], recipe: dict | None = None) -> Path:
        """Run `make(tmp_folder)` to fill a new entry, then publish it. If `make` raises, nothing is kept and the
        error goes on (loud). If the same entry appeared meanwhile (another app made it), that one is used."""
        folder = self.path(kind, key)
        if self.get(kind, key):
            return folder
        tmp = folder.parent / f".tmp-{key[:16]}-{uuid.uuid4().hex[:8]}"
        tmp.mkdir(parents=True)
        t0 = time.perf_counter()
        try:
            make(tmp)
            files = [p.name for p in tmp.iterdir()]
            if not files:
                raise RostrumError(codes.JOB_FAILED, f"cache {kind}", key[:12], "the job made no files")
            meta = {"kind": kind, "key": key, "recipe": recipe or {}, "files": files, "bytes": _size(tmp),
                    "made": time.strftime("%Y-%m-%dT%H:%M:%S"), "took_s": round(time.perf_counter() - t0, 3)}
            (tmp / ENTRY).write_text(json.dumps(meta, indent=1), encoding="utf-8")
            os.utime(tmp / ENTRY, (self.clock(), self.clock()))     # entry.json's time = when last used
            try:
                tmp.rename(folder)
            except OSError:
                if not (folder / ENTRY).is_file():
                    raise
                shutil.rmtree(tmp, ignore_errors=True)        # made twice at once: the first one stands
        except BaseException:
            shutil.rmtree(tmp, ignore_errors=True)
            raise
        self.trim()
        return folder

    def entries(self) -> list[tuple[float, int, Path]]:
        """(last used, bytes, folder) of every entry."""
        out = []
        if not self.root.is_dir():
            return out
        for meta in self.root.glob(f"*/*/{ENTRY}"):
            try:
                st, size = meta.stat(), json.loads(meta.read_text(encoding="utf-8")).get("bytes", 0)
            except (OSError, ValueError):
                continue
            out.append((st.st_mtime, int(size), meta.parent))
        return out

    def trim(self, keep: set | None = None) -> int:
        """Remove least recently used entries until under the cap; `keep` = folders a running job uses.
        Returns bytes freed."""
        entries = sorted(self.entries())
        total, freed, now = sum(e[1] for e in entries), 0, self.clock()
        for used, size, folder in entries:
            if total <= self.cap:
                break
            if now - used < KEEP_RECENT_S or (keep and folder in keep):
                continue
            shutil.rmtree(folder, ignore_errors=True)
            total, freed = total - size, freed + size
        return freed

    def stats(self) -> dict:
        entries = self.entries()
        return {"root": str(self.root), "entries": len(entries), "bytes": sum(e[1] for e in entries), "cap": self.cap}


CACHE = Cache()
