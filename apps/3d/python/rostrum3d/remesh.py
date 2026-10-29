"""Make a clean mesh (SPEC PR4, ZBrush's ZRemesher): a clay's surface, as the core draws it, rebuilt as an even mesh of
four-sided faces that follow its shape, ready for export, rigging or editing as a mesh. Instant Meshes does it (Jakob,
Tarini, Panozzo, Sorkine-Hornung 2015; BSD-3, through the `pyinstantmeshes` package, BSD-3).

    raw = surface(doc, "head")                         # the clay's welded surface from the engine (ops_mesh's hook)
    key = key_of(raw, 4000)
    folder = compute(raw, 4000, key, progress=…, stopped=…)  # once per surface and face count, into the shared cache
    points, faces = read(folder)

The work runs in its own process (remesh_worker.py), so a person's Cancel ends it at once (by its own handle, never by
name) and a crash inside the library can't take the window down. Analysed once, stored as data: the result sits in the
content-keyed cache (kind "cleanmesh", keyed by the surface itself, the face count and this module's version), so
asking again for the same clay and count costs nothing; `clay.clean_mesh` then only adds the mesh item.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from rostrum_core.cache import CACHE, cache_key

KIND = "cleanmesh"
VERSION = "rostrum-remesh@1"           # bump when the worker's settings or the reading change
FACES = (100, 200_000)                  # the face counts a person may ask for
OBJ = "clean.obj"


class RemeshError(RuntimeError):
    """The clean mesh could not be made: what failed and what to do."""


class Cancelled(RemeshError):
    pass


_LAST: dict = {}        # {"key": (clay id, the document's hash), "raw": …}: the window's job and the operation after it


def surface(doc: dict, clay_id: str) -> dict:
    """The clay's surface as drawn: {"points", "faceCounts", "faceIndices"} from the engine (geometry, v1.33). The
    last one is kept while the document is exactly the same, so the window's job and the clay.clean_mesh it calls
    when done read a clay of a million triangles from the engine once, not twice."""
    from . import ops_mesh
    if ops_mesh._GEOMETRY is None:
        raise RemeshError("there is no engine to read the clay from (run it in the app or through the 3D MCP server)")
    key = (clay_id, hashlib.sha256(json.dumps(doc, sort_keys=True, default=str).encode()).hexdigest())
    if _LAST.get("key") != key:
        _LAST.clear()
        _LAST.update(key=key, raw=ops_mesh._GEOMETRY(doc, clay_id))
    return _LAST["raw"]


def key_of(raw: dict, faces: int) -> str:
    """The cache key: the surface's own content, the face count asked for, this module's version."""
    h = hashlib.sha256()
    h.update(np.asarray(raw["points"], np.float32).tobytes())
    h.update(np.asarray(raw["faceIndices"], np.int32).tobytes())
    return cache_key(KIND, VERSION, [h.hexdigest()], {"faces": int(faces)})


def cached(key: str) -> Path | None:
    return CACHE.get(KIND, key)


def compute(raw: dict, faces: int, key: str, progress=lambda line: None, stopped=lambda: False,
            started=lambda proc: None) -> Path:
    """The cache folder holding the clean mesh for `raw` at about `faces` faces (made now when missing). `progress`
    gets plain lines; `stopped()` true ends the worker and raises Cancelled; `started(proc)` gets the worker process."""
    if not FACES[0] <= int(faces) <= FACES[1]:
        raise RemeshError(f"faces {faces} is outside {FACES[0]}..{FACES[1]}")
    if (got := cached(key)) is not None:
        return got
    tris = _triangles(raw)
    if len(tris) < 4:
        raise RemeshError("the clay's surface has fewer than 4 triangles; sculpt something first")

    def make(tmp: Path):
        src = tmp / "surface.obj"
        _write_obj(src, np.asarray(raw["points"], np.float32), tris)
        progress(f"rebuilding {len(tris):,} triangles as about {faces:,} four-sided faces")
        _run(src, tmp / OBJ, int(faces), progress, stopped, started)
        src.unlink()
        (tmp / "worker.log").unlink()
        pts, polys = _read_obj(tmp / OBJ)
        (tmp / "facts.json").write_text(json.dumps({"points": len(pts), "faces": len(polys),
                                                    "from": len(tris)}), encoding="utf-8")
    return CACHE.put(KIND, key, make, recipe={"faces": int(faces), "triangles": len(tris)})


def read(folder: Path) -> tuple[list[list[float]], list[list[int]]]:
    pts, polys = _read_obj(Path(folder) / OBJ)
    return pts.tolist(), polys


def _triangles(raw: dict) -> np.ndarray:
    counts, idx = raw["faceCounts"], raw["faceIndices"]
    out, i = [], 0
    for c in counts:                      # a fan per face (the clay's surface is all triangles already)
        for k in range(1, c - 1):
            out.append((idx[i], idx[i + k], idx[i + k + 1]))
        i += c
    return np.asarray(out, np.int64)


def _write_obj(path: Path, pts: np.ndarray, tris: np.ndarray):
    with open(path, "w", encoding="ascii", newline="\n") as f:
        f.write("".join(f"v {x:.7g} {y:.7g} {z:.7g}\n" for x, y, z in pts))
        f.write("".join(f"f {a + 1} {b + 1} {c + 1}\n" for a, b, c in tris))


def _read_obj(path: Path) -> tuple[np.ndarray, list[list[int]]]:
    pts, polys = [], []
    for line in path.read_text(encoding="ascii").splitlines():
        if line.startswith("v "):
            pts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("f "):
            polys.append([int(w.split("/")[0]) - 1 for w in line.split()[1:]])
    if not polys:
        raise RemeshError(f"Instant Meshes made no faces ({path})")
    return np.asarray(pts, np.float64), polys


def _run(src: Path, out: Path, faces: int, progress, stopped, started):
    """remesh_worker.py in its own process; polled, so Cancel ends it within a tenth of a second. What it says goes
    to a file beside it (a pipe nobody reads while it runs fills up and stalls the worker)."""
    cmd = [sys.executable, "-I", str(Path(__file__).with_name("remesh_worker.py")), str(src), str(out), str(faces)]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    log = out.with_name("worker.log")
    with open(log, "wb") as said_to:
        proc = subprocess.Popen(cmd, stdout=said_to, stderr=subprocess.STDOUT, creationflags=flags)
    started(proc)
    t0 = time.monotonic()
    try:
        while proc.poll() is None:
            if stopped():
                proc.kill()
                proc.wait()
                raise Cancelled("cancelled")
            time.sleep(0.1)
            progress(f"rebuilding the surface · {time.monotonic() - t0:.0f} s")
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait()
    said = log.read_text(encoding="utf-8", errors="replace").strip()
    if proc.returncode != 0 or not out.is_file():
        last = said.splitlines()[-1] if said else f"exit code {proc.returncode}"
        raise RemeshError(f"Instant Meshes failed: {last}")
