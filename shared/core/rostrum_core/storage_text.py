"""The document file's text and names: canonical JSON (whole or in pieces), its hash, the files' paths, an atomic write
(see storage.py for the layout)."""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from pathlib import Path

from . import filestamps
from .errors import RostrumError, codes


VERSION_FILE = Path(__file__).resolve().parents[3] / "VERSION"   # <root>/shared/core/rostrum_core/storage.py


def app_version() -> str:
    """The Rostrum version saving files (the installer's and Help → About's number too). Missing is loud."""
    try:
        return VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError as e:
        raise RostrumError(codes.INTERNAL, "save", str(VERSION_FILE), f"can't be read ({e})",
                           hint="The app's VERSION file is missing; reinstall Rostrum.") from e


def canonical(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


_CHUNK = 64


def canonical_pieces(data):
    """canonical(data) as pieces (a generator) that join to exactly the same text, each made by one short call: a
    window makes a big document's text a few milliseconds at a time between the person's events (doc_write.py).
    Items holding child items are opened up; a long list is written 64 entries at a time."""
    if _parent(data):
        for n, k in enumerate(sorted(data)):
            yield ("{" if not n else ",") + json.dumps(k, ensure_ascii=False) + ":"
            yield from canonical_pieces(data[k])
        yield "}"
    elif type(data) is list and (len(data) > _CHUNK or any(map(_parent, data))):
        yield "["
        for n in range(0, len(data), _CHUNK):
            part = data[n:n + _CHUNK]
            if any(map(_parent, part)):
                for m, x in enumerate(part):
                    if n or m:
                        yield ","
                    yield from canonical_pieces(x)
            else:
                yield ("," if n else "") + canonical(part)[1:-1]
        yield "]"
    else:
        yield canonical(data)


def _parent(v) -> bool:
    return type(v) is dict and any(type(x) is list and x and type(x[0]) is dict for x in v.values())


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def doc_hash(data) -> str:
    return _sha(canonical(data))


def paths(folder, item, ext) -> dict:
    folder = Path(folder)
    return {"doc": folder / "docs" / f"{item}{ext}", "history": folder / ".rostrum" / f"{item}.history.jsonl",
            "script": folder / ".rostrum" / f"{item}.script.json"}


def write_atomic(path: Path, text: str, tries: int = 20):
    filestamps.forget(path)              # this process's own write: a kept "unchanged" answer about it is old
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.partial")   # one per writer: no collisions
    tmp.write_text(text, encoding="utf-8")
    for n in range(tries):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:          # Windows: someone has the file open; wait a little
            if n == tries - 1:
                raise RostrumError(codes.INTERNAL, "save", str(path), "stayed locked by another program",
                                   hint=f"The new version is kept at {tmp}.")
            time.sleep(0.1)


def _read_json(path: Path, where: str):
    try:
        text = path.read_text(encoding="utf-8")
        return text, json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        raise RostrumError(codes.CHECK_FAILED, where, str(path), f"can't be read: {e}") from e
