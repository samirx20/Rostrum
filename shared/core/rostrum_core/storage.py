"""Saving and opening a document (OPERATIONS.md § 6, project-service CONTRACT.md § 1).

In the project folder:
    docs/<item><ext>                    the document: {"format", "version", "doc"}, plain readable JSON
    .rostrum/<item>.history.jsonl       line 1 = the document when history began; then one change per line,
                                        and {"version": name, "at": seq} lines for named versions
    .rostrum/<item>.script.json         what each script produced last time (for the § 7 merge)

Every file is written whole (temp file, then rename; retried while Windows holds the file). On open, a file
that differs from the history's last step is recorded first as a change by `outside`.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import time
from pathlib import Path

from .errors import RostrumError, codes
from .who import Who


def canonical(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def doc_hash(data) -> str:
    return hashlib.sha256(canonical(data).encode("utf-8")).hexdigest()[:16]


def paths(folder, item, ext) -> dict:
    folder = Path(folder)
    return {"doc": folder / "docs" / f"{item}{ext}", "history": folder / ".rostrum" / f"{item}.history.jsonl",
            "script": folder / ".rostrum" / f"{item}.script.json"}


def write_atomic(path: Path, text: str, tries: int = 20):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".partial")
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


def save(doc):
    if doc.folder is None or doc.item_id is None:
        raise RostrumError(codes.BAD_ARGUMENT, "save", "the document", "has no project folder or item id")
    p, kind = paths(doc.folder, doc.item_id, doc.kind.ext), doc.kind
    lines = [json.dumps({"format": kind.format, "version": kind.version, "base": doc.base}, ensure_ascii=False)]
    lines += [json.dumps(c.to_dict(), ensure_ascii=False) for c in doc.history.changes]
    lines += [json.dumps({"version": n, "at": s}) for n, s in doc.history.versions.items()]
    write_atomic(p["history"], "\n".join(lines) + "\n")
    write_atomic(p["script"], json.dumps(doc.script_bases, indent=1, ensure_ascii=False))
    write_atomic(p["doc"], json.dumps({"format": kind.format, "version": kind.version, "doc": doc.data},
                                      indent=1, ensure_ascii=False))


def _read_json(path: Path, where: str):
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError) as e:
        raise RostrumError(codes.CHECK_FAILED, where, str(path), f"can't be read: {e}") from e


def _check_format(kind, head, path):
    if head.get("format") != kind.format:
        raise RostrumError(codes.BAD_ARGUMENT, "open", str(path), f"is a {head.get('format')!r} file",
                           [kind.format])
    if head.get("version", 0) > kind.version:
        raise RostrumError(codes.CHECK_FAILED, "open", str(path), f"was saved by a newer version "
                           f"({head['version']} > {kind.version})", hint="Update Rostrum to open it.")


def open_doc(cls, folder, item, kind):
    from .history import Change
    p = paths(folder, item, kind.ext)
    file = _read_json(p["doc"], "open")
    _check_format(kind, file, p["doc"])
    doc = cls(kind, file["doc"], folder, item)
    if not p["history"].exists():
        return doc
    raw = p["history"].read_text(encoding="utf-8").splitlines()
    for n, line in enumerate(raw, 1):
        try:
            entry = json.loads(line)
            if n == 1:
                _check_format(kind, entry, p["history"])
                doc.base = entry["base"]
            elif "version" in entry and "seq" not in entry:
                doc.history.versions[entry["version"]] = entry["at"]
            else:
                doc.history.add(Change.from_dict(entry))
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            raise RostrumError(codes.CHECK_FAILED, "open", f"{p['history']} line {n}",
                               f"is damaged ({type(e).__name__}: {e})", hint="Nothing was saved over it.") from e
    if p["script"].exists():
        doc.script_bases = _read_json(p["script"], "open")
    replayed = doc.at_step(doc.seq)
    if doc.seq and doc_hash(replayed) != doc.history.changes[-1].hash_after:
        raise RostrumError(codes.CHECK_FAILED, "open", str(p["history"]), "doesn't add up to its own last step")
    if doc_hash(replayed) != doc_hash(file["doc"]):
        _record_outside(doc, replayed, file["doc"])
    return doc


def _record_outside(doc, replayed, on_disk):
    """The file was changed by something without history: record the difference first, then carry on."""
    from .diff import diff
    edits = diff(replayed, on_disk, doc.kind.lists)
    doc.data = copy.deepcopy(replayed)
    doc.commit(copy.deepcopy(on_disk), edits, Who.outside("file changed outside Rostrum"), "Changed outside Rostrum")
