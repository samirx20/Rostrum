"""The cleanup chain: a clip's settings become steps, each step one cache entry made from the previous step's file.

A step is a module with STEP (name), ENGINE ("model@version"), run(src, folder, **settings) writing its files into
the new cache entry, output(**settings) (the file name to read on), optionally keyed(**settings) (what the key holds).
A recipe is a dict of the clip's cleanup fields: `stem` ("vocals" / "drums" / "bass" / "other"), `isolate` (keep only
the dialogue), `denoise` (0..1), `dereverb` (0..1). Zero / off / missing = that step is skipped.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from rostrum_core import RostrumError, codes
from rostrum_core.cache import Cache, cache_key, file_hash

STEMS = ("vocals", "drums", "bass", "other")
FIELDS = ("stem", "isolate", "denoise", "dereverb")


@dataclass
class Result:
    file: str
    generated: bool
    steps: list[dict] = field(default_factory=list)   # [{step, engine, file, generated, took_s}]


def recipe_of(clip: dict) -> dict:
    """The cleanup part of a clip (only the steps that are on)."""
    r = {}
    if clip.get("stem") in STEMS:
        r["stem"] = clip["stem"]
    if clip.get("isolate"):
        r["isolate"] = True
    for k in ("denoise", "dereverb"):
        if float(clip.get(k) or 0) > 0:
            r[k] = round(float(clip[k]), 3)
    return r


def needs_cleanup(clip: dict) -> bool:
    """True when the clip plays a cleaned take (it has a step and `useCleaned` is not switched off)."""
    return bool(recipe_of(clip)) and clip.get("useCleaned", True) is not False


def _steps(recipe: dict) -> list[tuple[str, dict]]:
    from . import dereverb, isolate, noise, stems
    out = []
    if recipe.get("stem"):
        out.append((stems, {"stem": recipe["stem"]}))
    elif recipe.get("isolate"):
        out.append((isolate, {}))
    if recipe.get("denoise"):
        out.append((noise, {"strength": recipe["denoise"]}))
    if recipe.get("dereverb"):
        out.append((dereverb, {"amount": recipe["dereverb"]}))
    return out


def _check(media, recipe):
    p = Path(media)
    if not p.is_file():
        raise RostrumError(codes.NOT_FOUND, "cleanup", str(media), "is not a file")
    bad = set(recipe) - set(FIELDS)
    if bad:
        raise RostrumError(codes.BAD_ARGUMENT, "cleanup", ", ".join(sorted(bad)), f"is not a cleanup field ({', '.join(FIELDS)})")
    if recipe.get("stem") and recipe["stem"] not in STEMS:
        raise RostrumError.not_found("cleanup", "stem", recipe["stem"], STEMS, in_="the stems")
    return p


def _walk(media, recipe, run: bool, progress=None) -> Result | None:
    src = _check(media, recipe)
    steps = _steps(recipe)
    if not steps:
        return Result(str(src), False, [])
    store, done, generated = Cache(), [], False
    for mod, settings in steps:
        keyed = getattr(mod, "keyed", lambda **s: s)(**settings)   # stems: one entry holds all four
        key = cache_key(f"cleanup.{mod.STEP}", mod.ENGINE, [file_hash(src)], keyed)
        entry = store.get("cleanup", key)
        made = False
        if not entry:
            if not run:
                return None
            if progress:
                progress(f"{mod.STEP}: {src.name}")
            entry = store.put("cleanup", key, lambda tmp, m=mod, s=src, st=settings: m.run(s, tmp, **st),
                              {"step": mod.STEP, "engine": mod.ENGINE, "input": str(src), **keyed})
            made = generated = True
        out = entry / mod.output(**settings)
        if not out.is_file():
            raise RostrumError(codes.JOB_FAILED, "cleanup", mod.STEP, f"left no {out.name} in {entry}")
        done.append({"step": mod.STEP, "engine": mod.ENGINE, "file": str(out), "generated": made})
        src = out
    return Result(str(src), generated, done)


def cached(media, recipe: dict) -> str | None:
    """The cleaned file if every step is already made, else None. Never runs a model."""
    r = _walk(media, recipe, run=False)
    return r.file if r else None


def make(media, recipe: dict, progress: Callable[[str], None] | None = None) -> Result:
    """The cleaned take: each missing step made once (model loaded for it and released), the rest from the cache."""
    return _walk(media, recipe, run=True, progress=progress)
