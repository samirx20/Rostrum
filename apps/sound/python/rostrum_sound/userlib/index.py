"""Indexing a sound folder once: every audio file read, cut into single sounds, each measured and given its kinds.

Stored in the shared content-keyed cache (rostrum_core.cache), never next to the user's files and never in a project:
  kind "sound-userlib"         one entry per file, keyed by the file's content, its name and folder words, and the
                               index version: the same file anywhere is analysed once
  kind "sound-userlib-folder"  one entry per folder, keyed by its path and every file's (path, size, time): an
                               unchanged folder is read back in one go without opening a single sound file
Only paths and measurements are kept; no audio is copied.

A file is split into its takes on the silences between them (a file with one sound is that sound, its silence
trimmed). A long take with no silence in it (a handling recording full of small sounds) goes through the cut pool
(sfx/pool.py `cut`, the same cutter and cache the agent's pool uses). An ambience stays whole; a whoosh, riser or
drone is split only on its silences.
A file that can't be read is reported in `skipped` with the reason, on every read of the index.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
from rostrum_core.cache import Cache, cache_key, file_hash

from ..listen.dsp import load_mono
from ..sfx.pool import SR, cut
from . import kinds, measure, meta

VERSION = 5
ENGINE = f"rostrum-sound-userlib@{VERSION}"

AUDIO = {".wav", ".wave", ".bwf", ".flac", ".ogg", ".aif", ".aiff", ".mp3"}
CONTINUOUS_S = 6.0                     # a take longer than this with no silence in it goes to the cut pool
MIN_S, QUIET_DB = 0.01, 30.0
FLOWING = {"whoosh", "riser", "drone"}  # sounds with no transient to cut on
CUT = {"mode": "hits", "max_s": 4.0, "min_s": 0.05, "per_file": 60, "min_snr": 18.0}
_LOADED: dict[str, dict] = {}         # folder -> its index, read once per process


def audio_files(folder: Path) -> list[Path]:
    return sorted(p for p in folder.rglob("*") if p.suffix.lower() in AUDIO and p.is_file())


def _bounds(x, path, about, cache_dir) -> list[tuple[int, int]]:
    """Where the single sounds are: takes split by silence; a take longer than CONTINUOUS_S (a handling recording
    full of small sounds) cut on its transients by the cut pool; a file named as a sound that flows (an ambience,
    a whoosh series, a riser, a drone) is never cut on transients, only on its silences. Takes more than
    QUIET_DB under the file's loudest are tails and noise, not sounds."""
    regs = [r for r in measure.regions(x, SR) if r[1] - r[0] >= MIN_S * SR]
    named = kinds.named(about)
    if not regs or "ambience" in named:
        return [(regs[0][0], regs[-1][1])] if regs else []
    flowing = bool(named & FLOWING)
    loudest = float(np.abs(x).max())
    out, cuts = [], None
    for a, b in regs:
        if float(np.abs(x[a:b]).max()) < loudest * 10 ** (-QUIET_DB / 20):
            continue
        if b - a <= CONTINUOUS_S * SR or flowing:
            out.append((a, b))
            continue
        cuts = cuts if cuts is not None else cut(path, cache_dir=cache_dir, **CUT)["cuts"]
        inside = [(int(c["start"] * SR), int(c["end"] * SR)) for c in cuts if a <= c["start"] * SR < b]
        out += inside or [(a, b)]
    return sorted(out)


def _analyse(path: Path, about: dict, cache_dir) -> dict:
    x = load_mono(path, SR)
    if x.size == 0:
        raise ValueError("the file has no audio")
    sounds = []
    for a, b in _bounds(x, path, about, cache_dir):
        m = measure.measure(x[a:b], SR)
        sounds.append({"start": round(a / SR, 4), "end": round(b / SR, 4), "file_s": round(x.size / SR, 4), **m,
                       "words": measure.words_of(m), **kinds.classify(about, m)})
    return {"about": about, "sounds": sounds}


def file_sounds(path, root, cache_dir=None) -> tuple[list[dict], bool]:
    """(the sounds in one file, came from the cache)."""
    path, root = Path(path), Path(root)
    about = meta.about(path, root)                  # the words decide the kinds, so they are part of the key
    store = Cache(cache_dir)
    key = cache_key("sound-userlib", ENGINE, [file_hash(path), path.name, about["folder"]],
                    {"continuous_s": CONTINUOUS_S, "min_s": MIN_S, "quiet_db": QUIET_DB, **CUT})
    entry = store.get("sound-userlib", key)
    if entry:
        data, cached = json.loads((entry / "sounds.json").read_text(encoding="utf-8")), True
    else:
        data, cached = _analyse(path, about, cache_dir), False
        store.put("sound-userlib", key, lambda d: (d / "sounds.json").write_text(json.dumps(data), encoding="utf-8"),
                  {"engine": ENGINE, "file": str(path)})
    a = data["about"]
    words = " ".join(w for w in (a["name"], a["meta"]) if w)
    return [{"path": str(path), "about": words, "folder_words": a["folder"], "ucs": a["ucs"], **s}
            for s in data["sounds"]], cached


def index_folder(folder, cache_dir=None, progress=None) -> dict:
    """Index `folder` (all audio files under it). Returns {"folder", "files", "sounds", "skipped", "from_cache"
    (the whole folder came back from the cache), "files_from_cache", "took_s"}. `progress(done, total)` is called
    after each file when the folder is (re)analysed."""
    t0 = time.perf_counter()
    root = Path(folder).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"{root}: sound folder not found")
    files = audio_files(root)
    stamp = [[p.relative_to(root).as_posix(), p.stat().st_size, p.stat().st_mtime_ns] for p in files]
    store = Cache(cache_dir)
    key = cache_key("sound-userlib-folder", ENGINE, [str(root)], {"files": stamp})
    entry = store.get("sound-userlib-folder", key)
    if entry:
        out = {**json.loads((entry / "index.json").read_text(encoding="utf-8")), "from_cache": True,
               "files_from_cache": len(files)}
    else:
        sounds, skipped, cached = [], [], 0
        for i, p in enumerate(files):
            try:
                found, hit = file_sounds(p, root, cache_dir)
                sounds += found
                cached += hit
            except Exception as e:  # noqa: BLE001  one unreadable file is reported, the rest still indexed
                skipped.append({"path": str(p), "why": f"{type(e).__name__}: {e}"})
            if progress:
                progress(i + 1, len(files))
        body = {"folder": str(root), "files": len(files), "sounds": sounds, "skipped": skipped}
        store.put("sound-userlib-folder", key,
                  lambda d: (d / "index.json").write_text(json.dumps(body), encoding="utf-8"),
                  {"engine": ENGINE, "folder": str(root), "files": len(files)})
        out = {**body, "from_cache": False, "files_from_cache": cached}
    out["took_s"] = round(time.perf_counter() - t0, 3)
    _LOADED[str(root)] = out
    return out


def library(folders, cache_dir=None) -> list[dict]:
    """Every sound in `folders` (indexed now if this process hasn't read them yet)."""
    out = []
    for f in folders:
        root = str(Path(f).resolve())
        out += (_LOADED.get(root) or index_folder(root, cache_dir))["sounds"]
    return out


def forget():
    """Drop what this process has read (the next search reads the cache again)."""
    _LOADED.clear()
