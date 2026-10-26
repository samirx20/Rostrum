"""Dab files: a stroke's dabs exactly as applied, kept beside the document (CONTRACT CL1 § 2; the core reads and
writes the same format, core/src/clay_dabs.*).

    <project folder>/clay/<hash>.dabs     little-endian: b"CLD1", uint32 n, then n × 9 float32
                                          a.xyz n.xyz b.xyz (surface point, normal, pull / crease direction)

`<hash>` = the first 32 hex of the whole file's sha256: content-addressed, so a file is never rewritten and never
deleted by undo (the step that names it may come back). A stroke's step stores the reference "clay/<hash>.dabs".
"""
from __future__ import annotations

import hashlib
import os
import struct
import uuid
from pathlib import Path

MAGIC, FOLDER, SUFFIX = b"CLD1", "clay", ".dabs"
HEADER = struct.Struct("<4sI")


def pack(rows) -> bytes:
    """The file's bytes for [[ax, ay, az, nx, ny, nz, bx, by, bz], …]."""
    flat = [float(v) for r in rows for v in r]
    if len(flat) != 9 * len(rows):
        raise ValueError("a dab is 9 numbers: a.xyz n.xyz b.xyz")
    return HEADER.pack(MAGIC, len(rows)) + struct.pack(f"<{len(flat)}f", *flat)


def unpack(data: bytes) -> list[list[float]]:
    magic, n = HEADER.unpack_from(data)
    if magic != MAGIC or len(data) != HEADER.size + 36 * n:
        raise ValueError(f"not a dabs file (magic {magic!r}, {len(data)} bytes for {n} dabs)")
    flat = struct.unpack_from(f"<{9 * n}f", data, HEADER.size)
    return [list(flat[i:i + 9]) for i in range(0, 9 * n, 9)]


def name_of(data: bytes) -> str:
    """The reference a file of these bytes has: "clay/<first 32 hex of sha256>.dabs"."""
    return f"{FOLDER}/{hashlib.sha256(data).hexdigest()[:32]}{SUFFIX}"


def path(folder, ref: str) -> Path:
    """The file a reference names, inside the project folder (a reference that leaves it fails loudly)."""
    if not (isinstance(ref, str) and ref.startswith(FOLDER + "/") and ref.endswith(SUFFIX) and "/" not in ref[5:]):
        raise ValueError(f'"{ref}" is not a dabs reference ("clay/<hash>.dabs")')
    return Path(folder) / FOLDER / ref[len(FOLDER) + 1:]


def write(folder, rows) -> str:
    """Save dabs into the project; their reference. Same dabs, same file: an existing one is left as it is."""
    data = pack(rows)
    ref = name_of(data)
    out = path(folder, ref)
    if not out.is_file():
        out.parent.mkdir(parents=True, exist_ok=True)
        tmp = out.with_name(f"{out.name}.{uuid.uuid4().hex[:8]}.partial")
        tmp.write_bytes(data)
        os.replace(tmp, out)                       # whole or nothing: a reader never sees half a file
    return ref


def read(folder, ref: str) -> list[list[float]]:
    f = path(folder, ref)
    if not f.is_file():
        raise FileNotFoundError(f'the dabs file "{ref}" is missing from the project ({f})')
    return unpack(f.read_bytes())


def tidy(calls: list[dict], folder=None) -> list[dict]:
    """Inline dabs a call gives (`dabList`) are saved as a file and the call names it (`dabs`), when the document has
    a folder; without one they stay inline. Only how the dabs are written changes, never what they are."""
    if folder is None:
        return calls

    def fix(v):
        if isinstance(v, dict):
            v = {k: fix(x) for k, x in v.items()}
            if v.get("dabList"):
                v["dabs"] = write(folder, v.pop("dabList"))
            return v
        return [fix(x) for x in v] if isinstance(v, list) else v
    return [{**c, "args": fix(c["args"])} for c in calls]
