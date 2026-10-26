"""A clay → its scene node's steps and cache (CONTRACT CL1 § 3; compile.py calls `finish`). Python makes each step's
`key`, a chain hash: the core only compares keys to tell what it already holds (same keys → nothing to do, a longer
chain → apply the rest, a shorter one → undo), so the keys must stay the same for the same steps, whatever machine
or folder: a stroke's dabs count by their file's hash name, never its absolute path, and inline dabs by the name
their file would have (clay_dabs.name_of), so tidying them into a file changes no key.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rostrum_core.cache import CACHE, cache_key

from . import clay_dabs, clay_detail
from .clay_fields import CLAY, STEP as CLAYSTEP

VERSION = "rostrum3d-clay@5"          # bump when the core builds the same steps differently (the cache key holds it)
BRUSH = {p.name for p in CLAY if p.group == "Brush"}          # the next stroke's settings: never sent
STROKE = ("falloff", "spacing", "frontOnly", "invert")       # CL2's stroke settings (a CL1 step has the defaults)
_DEFAULT = {p.name: p.default for p in CLAYSTEP if p.name in STROKE}


def _v(xs) -> list[float]:
    return [float(v) for v in xs]          # 1 and 1.0 are the same step: the same key either way


def _step(s: dict) -> dict:
    """One step as the core reads it, its dabs by hash name ("dabs": "clay/<hash>.dabs") for the key."""
    mirror = s.get("symmetry") == "x"
    if s["step"] == "piece":
        at = _v(s["at"])
        to = _v(s["to"]) if s.get("shape") == "capsule" and s.get("to") else at
        return {"kind": "piece", "op": s["mode"], "a": at, "b": to, "radius": float(s["radius"]),
                "blend": float(s["blend"]), "mirror": mirror}
    out = {"kind": "stroke", "op": s["brush"], "radius": float(s["size"]), "strength": float(s["strength"]),
           "mirror": mirror, "accumulate": bool(s["accumulate"]),
           "falloff": float(s.get("falloff", _DEFAULT["falloff"])), "spacing": float(s.get("spacing", _DEFAULT["spacing"])),
           "frontOnly": bool(s.get("frontOnly", _DEFAULT["frontOnly"])), "invert": bool(s.get("invert", _DEFAULT["invert"]))}
    if s.get("dabs"):
        out["dabs"] = s["dabs"]
    elif s.get("dabList"):
        out["dabs"] = clay_dabs.name_of(clay_dabs.pack(s["dabList"]))
        out["dabList"] = s["dabList"]
    else:
        out["path"], out["dir"] = [_v(q) for q in s["path"]], _v(s["dir"])
    return out


def chain(steps: list[dict]) -> list[dict]:
    """The steps as the core reads them, each with its key: sha256 of (previous key + the step's canonical JSON),
    first 24 hex. Inline dabs are left out of the hashed text (their name stands for them)."""
    out, prev = [], ""
    for s in steps:
        step = _step(s)
        canon = json.dumps({k: v for k, v in step.items() if k != "dabList"}, sort_keys=True, separators=(",", ":"))
        prev = hashlib.sha256((prev + canon).encode("utf-8")).hexdigest()[:24]
        out.append({"key": prev, **step})
    return out


def cache_file(last_key: str, detail: float) -> Path:
    """Where the core keeps a built clay: the shared cache's root / clay / <key> / clay.vdb (the core writes it)."""
    return CACHE.path("clay", cache_key("clay.volume", VERSION, [last_key], {"detail": detail})) / "clay.vdb"


def finish(node: dict, item: dict, folder=None, data: dict | None = None):
    """Turn a compiled clay node into the contract's: no brush settings, `detail` the number to build at (worked out
    from `data`'s shots when it follows the camera, clay_detail.py), smooth normals, its keyed steps (a dabs file as
    its absolute path in the project, inline dabs as `dabList`), and its cache file."""
    for name in BRUSH | {"detailMode"}:
        node["props"].pop(name, None)
    node["props"]["detail"] = clay_detail.detail(data or {}, item, folder)
    node["props"]["smooth"] = True
    steps = chain(item.get("steps", []))
    for s in steps:
        if "dabList" in s:
            del s["dabs"]                                     # inline: the core reads the list
        elif "dabs" in s:
            if folder is None:
                raise ValueError(f'clay {item["id"]}: a stroke names the dabs file "{s["dabs"]}", but the document '
                                 "has no project folder to find it in (save it into a project first)")
            s["dabs"] = str(clay_dabs.path(folder, s["dabs"]))
    node["steps"] = steps
    node["cache"] = str(cache_file(steps[-1]["key"], node["props"]["detail"])) if steps else ""
