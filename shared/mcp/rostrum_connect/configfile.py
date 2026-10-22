"""Read and write an agent's config file by structure, never by text replace. Never drops a person's comments."""
from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

import tomlkit


class ConnectError(Exception):
    """A failure the person can read: a plain sentence saying what went wrong and what to do."""


@dataclass
class Doc:
    data: object            # dict (json) or tomlkit document
    comments: bool = False  # the file had comments (jsonc)
    indent: object = 2      # spaces, or "\t"
    crlf: bool = False
    final_newline: bool = True


def strip_jsonc(text: str) -> tuple[str, bool]:
    """Text without comments and trailing commas (strings respected), and whether there were comments."""
    out: list[str] = []
    i, n, found = 0, len(text), False
    while i < n:
        c = text[i]
        if c == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            out.append(text[i:j + 1])
            i = j + 1
        elif text.startswith("//", i):
            found = True
            while i < n and text[i] != "\n":
                i += 1
        elif text.startswith("/*", i):
            found = True
            end = text.find("*/", i + 2)
            i = n if end < 0 else end + 2
        else:
            if c in "}]":                            # a comma right before a closer is a trailing comma
                k = len(out) - 1
                while k >= 0 and (not out[k].strip() or out[k] == ","):
                    if out[k] == ",":
                        del out[k]
                        break
                    k -= 1
            out.append(c)
            i += 1
    return "".join(out), found


def read(path: Path, fmt: str) -> Doc:
    path = Path(path)
    if not path.exists():
        return Doc(tomlkit.document() if fmt == "toml" else {})
    text = path.read_text(encoding="utf-8-sig")
    doc = Doc(None, crlf="\r\n" in text, final_newline=text.endswith("\n") or not text.strip())
    m = re.search(r"\n([ \t]+)\S", text)
    doc.indent = "\t" if m and "\t" in m.group(1) else (len(m.group(1)) if m else 2)
    try:
        if fmt == "toml":
            doc.data = tomlkit.parse(text)
        elif not text.strip():
            doc.data = {}
        else:
            body, doc.comments = strip_jsonc(text) if fmt == "jsonc" else (text, False)
            doc.data = json.loads(body)
    except Exception as e:                           # tomlkit and json raise different errors
        raise ConnectError(f"{path} can't be read ({e}). Rostrum leaves it as it is; fix the file or add it by hand.")
    if not isinstance(doc.data, dict):
        raise ConnectError(f"{path} doesn't hold a settings table. Rostrum leaves it as it is; add it by hand.")
    return doc


def write(path: Path, fmt: str, doc: Doc, by_hand: str = "") -> None:
    path = Path(path)
    if doc.comments:
        raise ConnectError(f"{path} has comments, which Rostrum won't remove. Add it by hand: {by_hand or 'see the guide'}")
    if fmt == "toml":
        text = tomlkit.dumps(doc.data).rstrip() + ("\n" if doc.final_newline else "")   # tomlkit leaves a blank line behind
    else:
        text = json.dumps(doc.data, indent=doc.indent, ensure_ascii=False)
        text += "\n" if doc.final_newline else ""
        text = text.replace("\n", "\r\n") if doc.crlf else text
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=path.name + ".", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except OSError as e:
        Path(tmp).unlink(missing_ok=True)
        raise ConnectError(f"Couldn't write {path} ({e}). Nothing was changed.")


def backup_dir(agent_id: str) -> Path:
    from .agents import expand
    base = os.environ.get("ROSTRUM_BACKUP_DIR")
    return Path(base, agent_id) if base else expand("%LOCALAPPDATA%/Rostrum/agent-backups") / agent_id


def backups(agent_id: str, filename: str) -> list[Path]:
    """This file's backups, oldest first."""
    folder = backup_dir(agent_id)
    found = folder.glob(f"*-{filename}") if folder.is_dir() else []
    return sorted(found, key=lambda p: p.stat().st_mtime_ns)


def backup(path: Path, agent_id: str) -> Path | None:
    """Copy the file aside before any change. None when there is no file yet."""
    path = Path(path)
    if not path.is_file():
        return None
    folder = backup_dir(agent_id)
    folder.mkdir(parents=True, exist_ok=True)
    stamp, n = time.strftime("%Y%m%d-%H%M%S"), 1
    dest = folder / f"{stamp}-{path.name}"
    while dest.exists():
        n += 1
        dest = folder / f"{stamp}-{n}-{path.name}"
    shutil.copy2(path, dest)
    return dest


def table(data, key: tuple, create: bool = False, fmt: str = "json"):
    """The servers table inside `data` (None when missing and not `create`)."""
    node = data
    for k in key:
        if k not in node:
            if not create:
                return None
            node[k] = tomlkit.table(True) if fmt == "toml" else {}
        node = node[k]
    return node
