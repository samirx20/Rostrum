"""A clay → its scene node's steps and cache (CONTRACT CL1 § 3; compile.py calls `finish`). Python makes each step's
`key`, a chain hash: the core only compares keys to tell what it already holds (same keys → nothing to do, a longer
chain → apply the rest, a shorter one → undo), so the keys must stay the same for the same steps, whatever machine
or folder: a stroke's dabs count by their file's hash name, never its absolute path, and inline dabs by the name
their file would have (clay_dabs.name_of), so tidying them into a file changes no key. A hidden step is left out
(the steps after it key without it); a piece made from an item keys by that item's fields as they are now
(clay_shapes.source_key), so changing the item rebuilds the clay.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rostrum_core.cache import CACHE, cache_key

from . import clay_dabs, clay_detail, clay_shapes
from .clay_fields import CLAY, STEP as CLAYSTEP

VERSION = "rostrum3d-clay@6"          # bump when the core builds the same steps differently (the cache key holds it)
BRUSH = {p.name for p in CLAY if p.group == "Brush"}          # the next stroke's settings: never sent
STROKE = ("falloff", "spacing", "frontOnly", "invert")       # CL2's stroke settings (a CL1 step has the defaults)
_DEFAULT = {p.name: p.default for p in CLAYSTEP if p.name in STROKE}


def _v(xs) -> list[float]:
    return [float(v) for v in xs]          # 1 and 1.0 are the same step: the same key either way


def _piece(s: dict, mirror: bool, items: dict) -> dict:
    """A drawn, spun or from-an-item piece (CL3 CONTRACT § 2)."""
    out = {"kind": "piece", "op": s["mode"], "blend": float(s["blend"]), "mirror": mirror, "shape": s["shape"]}
    if s["shape"] == "outline":
        out.update(plane=_v(s["plane"]), outline=[_v(q) for q in s["outline"]], puff=float(s.get("puff", 1.0)))
    elif s["shape"] == "spin":
        out.update(plane=_v(s["plane"]), profile=[_v(q) for q in s["profile"]])
    else:
        src = items.get(s["source"])
        out.update(source=s["source"], sourceKey=clay_shapes.source_key(src) if src else s.get("sourceKey", ""))
    return out


def _step(s: dict, items: dict) -> dict:
    """One step as the core reads it, its dabs by hash name ("dabs": "clay/<hash>.dabs") for the key."""
    mirror = s.get("symmetry") == "x"
    if s["step"] == "piece" and s.get("shape") in ("outline", "spin", "item"):
        return _piece(s, mirror, items)
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


def _items(data: dict | None) -> dict:
    out, stack = {}, list((data or {}).get("items", []))
    while stack:
        it = stack.pop()
        out[it["id"]] = it
        stack += it.get("children", []) + it.get("parts", [])
    return out


def chain(steps: list[dict], data: dict | None = None) -> list[dict]:
    """The shown steps as the core reads them, each with its key: sha256 of (previous key + the step's canonical
    JSON), first 24 hex. Inline dabs are left out of the hashed text (their name stands for them). `data`: the
    document, where a piece made from an item finds it (else its stored sourceKey stands)."""
    out, prev, items = [], "", _items(data)
    for s in steps:
        if s.get("hidden"):
            continue
        step = _step(s, items)
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
    steps = chain(item.get("steps", []), data)
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
