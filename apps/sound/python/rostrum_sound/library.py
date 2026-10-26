"""The installed sound library (`<assets>/sounds/<pack>/…`, settings.assets_dir) and what each sound in it is, so an agent can
choose a recording without hearing every file. One place answers "what is this file": a description from the
pack's own data when there is one (`library_data/<pack>.json`, shipped with the app, or a `takes.json` the pack
carries), else the words of its folders and file name; plus its length in seconds for recordings. A file the pack's
data lists as `retired` (whooshes, risers, reverse cymbals, sub drops, big impacts: PURPOSE.md, no cheap effects) is never offered.
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from . import settings

LIBRARY = settings.assets_dir() / "sounds"
DATA = Path(__file__).resolve().parent / "library_data"
AUDIO = {".wav", ".flac", ".ogg", ".mp3"}
KINDS = {"instruments": {".sfz"}, "recordings": AUDIO}


def _words(text: str) -> str:
    text = re.sub(r"\.(wav|flac|ogg|mp3|sfz)$", "", text, flags=re.I)
    return re.sub(r"\s+", " ", re.sub(r"[_\-]+", " ", text)).strip()


@lru_cache(maxsize=None)
def _known(pack: str) -> dict[str, dict]:
    """{file path inside the pack (forward slashes, lower case): its description row}."""
    rows = []
    shipped = DATA / f"{pack}.json"
    if shipped.is_file():
        data = json.loads(shipped.read_text(encoding="utf-8"))
        rows += data["files"] + [{"path": p, "retired": True} for p in data.get("retired", {}).get("files", [])]
    takes = LIBRARY / pack / "takes.json"
    if takes.is_file():
        for t in json.loads(takes.read_text(encoding="utf-8")):
            rel = Path(t["path"]).resolve().relative_to((LIBRARY / pack).resolve()).as_posix()
            rows.append({"path": rel, "title": t.get("label", ""), "author": t.get("author", ""),
                         "licence": t.get("licence", ""), "page": t.get("source_url", "")})
    return {r["path"].replace("\\", "/").lower(): r for r in rows}


@lru_cache(maxsize=4096)
def retired_name(path: str) -> str | None:
    """The category a shipped-and-retired recording had (e.g. "cinematic.riser") when `path` is one inside the library, else None."""
    try:
        rel = Path(path).resolve().relative_to(LIBRARY.resolve())
    except (ValueError, OSError):
        return None
    if len(rel.parts) < 2:
        return None
    pack, inner = rel.parts[0], Path(*rel.parts[1:]).as_posix().lower()
    if not _known(pack).get(inner, {}).get("retired"):
        return None
    shipped = DATA / f"{pack}.json"
    names = json.loads(shipped.read_text(encoding="utf-8")).get("retired", {}).get("names", {}) if shipped.is_file() else {}
    return next((v for k, v in names.items() if k.lower() == inner), "a transition sound")


def _seconds(p: Path) -> float | None:
    try:
        return _length(str(p), p.stat().st_mtime_ns)
    except OSError:
        return None


@lru_cache(maxsize=4096)
def _length(path: str, modified: int) -> float | None:     # keyed on the file's time: a replaced file is read again
    try:
        import soundfile as sf
        return round(sf.info(path).duration, 2)
    except Exception:  # noqa: BLE001  an mp3 soundfile can't read: the length stays unknown, said as such
        return None


def describe(p: Path) -> dict:
    """One sound: path, pack, what it is (`about`), its category name when the pack has one, length, licence."""
    rel = p.relative_to(LIBRARY)
    pack, inner = rel.parts[0], Path(*rel.parts[1:]).as_posix()
    row = _known(pack).get(inner.lower(), {})
    about = row.get("title") or _words(" / ".join(Path(inner).parts))
    out = {"path": str(p), "pack": pack, "about": about}
    if row.get("name"):
        out["category"] = row["name"]
    if p.suffix.lower() in AUDIO:
        out["seconds"] = _seconds(p)
    for k in ("author", "licence", "page"):
        if row.get(k):
            out[k] = row[k]
    return out


def find(kind: str = "instruments", words: str = "") -> list[Path]:
    """Every installed file of `kind` whose path or description has all the words (case-insensitive)."""
    if not LIBRARY.is_dir():
        raise FileNotFoundError(f"the sound library is not installed at {LIBRARY}")
    want, ws = KINDS[kind], words.lower().split()
    return [p for p, suffix, text in _listing() if suffix in want and all(w in text for w in ws)]


def spread(kind: str = "recordings", limit: int = 20) -> list[Path]:
    """A spread of the installed files of `kind` for browsing with no words: from each pack in turn (sound effects,
    mallets, strings, kits ...) one file, then another from the middle of its list, up to `limit`, so a list is never one
    instrument's notes."""
    packs: dict[str, list[Path]] = {}
    for p in find(kind):
        packs.setdefault(p.relative_to(LIBRARY).parts[0], []).append(p)
    picks = [[files[0], files[len(files) // 2]] if len(files) > 1 else files for files in packs.values()]
    return list(dict.fromkeys(f[i] for i in range(2) for f in picks if i < len(f)))[:limit]


_LISTED: tuple = (None, (), [])     # (the library folder, [(folder, modified time)], [(path, suffix, searchable text)]) of the last walk


def _folders(root: Path) -> tuple:
    import os
    return tuple((d, os.stat(d).st_mtime_ns) for d, _, _ in os.walk(root))


def _unchanged(root: Path, folders: tuple) -> bool:
    """No folder of the last walk was changed: adding, removing or renaming a file or folder changes its folder's
    modified time, so a changed library is seen by the next search (a stat per folder, a few ms, not a walk)."""
    import os
    try:
        return all(os.stat(d).st_mtime_ns == m for d, m in folders)
    except OSError:
        return False


def _listing() -> list:
    """The library's files once (path, suffix, lower-case text of its path and description; retired ones left out),
    walked again only when a folder changed: one listing, never stale after a sound is added."""
    global _LISTED
    if _LISTED[0] != LIBRARY or not _unchanged(LIBRARY, _LISTED[1]):
        folders = _folders(LIBRARY)         # before the files, so a file added meanwhile shows at the next search
        _known.cache_clear()
        rows = []
        for p in sorted(LIBRARY.rglob("*")):
            if p.suffix.lower() not in AUDIO | KINDS["instruments"]:
                continue
            rel = p.relative_to(LIBRARY)
            row = _known(rel.parts[0]).get(Path(*rel.parts[1:]).as_posix().lower(), {})
            if not row.get("retired"):
                rows.append((p, p.suffix.lower(), " ".join([str(rel), row.get("title", ""), row.get("name", "")]).lower()))
        _LISTED = (LIBRARY, folders, rows)
    return _LISTED[2]
