"""What an agent's settings file looked like before Rostrum's first entry went in, so taking the last entry out
leaves the file as it was: noted at Add (`note`), read and forgotten at Remove (`tidy`). One small JSON beside the
backups: {"<file>": {"existed": bool, "was_empty": bool, "made_table": bool}}. Kept until Rostrum has no entry left in that file."""
from __future__ import annotations

import json
from pathlib import Path

from .configfile import backup_dir, read, table, write


def _path() -> Path:
    return backup_dir("_").parent / "before.json"


def _load() -> dict:
    p = _path()
    return json.loads(p.read_text(encoding="utf-8")) if p.is_file() else {}


def _save(data: dict) -> None:
    p = _path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, indent=1), encoding="utf-8")


def note(file: Path, fmt: str, key: tuple) -> None:
    """Call before Rostrum's change. Only the first Add counts (a second app or a re-add sees our own table)."""
    data = _load()
    if str(file) in data:
        return
    empty = not file.exists() or not file.read_bytes().strip()
    data[str(file)] = {"existed": file.exists(), "was_empty": empty, "made_table": empty or table(read(file, fmt).data, key) is None}
    _save(data)


def tidy(file: Path, fmt: str, key: tuple, drop_table, ours) -> None:
    """Call after a Remove. Once none of Rostrum's entries is left (`ours(entry)`), forget the note; if the table
    is then empty and Rostrum made it, take it (or the whole content of a file that was empty) out again."""
    data = _load()
    seen = data.get(str(file))
    doc = read(file, fmt)
    t = table(doc.data, key)
    if seen is None or any(ours(e) for e in (t or {}).values()):   # the other Rostrum app is still in there
        return
    if seen["made_table"] and t is not None and not t:
        drop_table(doc.data, key)
        if doc.data or not seen["was_empty"]:      # the agent's own settings are in it now: keep them
            write(file, fmt, doc)
        elif seen["existed"]:
            file.write_bytes(b"")
        else:
            file.unlink()
    del data[str(file)]
    _save(data)
