"""Dab files: a stroke's dabs exactly as applied, kept beside the document (CONTRACT CL1 § 2, CL2; the core reads and
writes the same format, core/src/clay_dabs.*).

    <project folder>/clay/<hash>.dabs     little-endian: b"CLD2", uint32 n, then n × 11 float32
                                          a.xyz n.xyz b.xyz (surface point, normal, pull / crease direction)
                                          radiusScale strengthScale (pen pressure; 1 1 without a pen)
                                          or the CL1 form: b"CLD1", uint32 n, n × 9 float32 (scales 1)

A row is 9 numbers (no pen: scales 1) or 11. Dabs that are all 9 numbers are written as CLD1, so the dabs CL1 wrote
keep their file names and their steps their keys; any 11-number row makes the file CLD2.

`<hash>` = the first 32 hex of the whole file's sha256: content-addressed, so a file is never rewritten and never
deleted by undo (the step that names it may come back). A stroke's step stores the reference "clay/<hash>.dabs".
"""
from __future__ import annotations

import hashlib
import os
import struct
import uuid
from pathlib import Path

FOLDER, SUFFIX = "clay", ".dabs"
WIDTH = {b"CLD1": 9, b"CLD2": 11}               # numbers per dab
HEADER = struct.Struct("<4sI")


def pack(rows) -> bytes:
    """The file's bytes for [[ax, ay, az, nx, ny, nz, bx, by, bz, (radiusScale, strengthScale)], …]."""
    if any(len(r) not in (9, 11) for r in rows):
        raise ValueError("a dab is 9 numbers (a.xyz n.xyz b.xyz) or 11 (+ radiusScale strengthScale)")
    wide = any(len(r) == 11 for r in rows)
    magic = b"CLD2" if wide else b"CLD1"
    flat = [float(v) for r in rows for v in (list(r) + [1.0, 1.0] if wide and len(r) == 9 else r)]
    return HEADER.pack(magic, len(rows)) + struct.pack(f"<{len(flat)}f", *flat)


def unpack(data: bytes) -> list[list[float]]:
    """The rows as stored: 9 numbers each from a CLD1 file (scales 1), 11 from a CLD2 one."""
    magic, n = HEADER.unpack_from(data)
    w = WIDTH.get(magic)
    if w is None or len(data) != HEADER.size + 4 * w * n:
        raise ValueError(f"not a dabs file (magic {magic!r}, {len(data)} bytes for {n} dabs)")
    flat = struct.unpack_from(f"<{w * n}f", data, HEADER.size)
    return [list(flat[i:i + w]) for i in range(0, w * n, w)]


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
