"""The sample packs RostrumSound can install: what each is, where it comes from and what each file's fingerprint is.

Data, ported from the OLD-EXPERIMENT experiment (its soundPacks.ts at d0b73b2): `library_data/packs/catalog.json` (title,
author, licence, page, credit line for CC-BY packs, and the source: a zip or archive pinned by sha256, or single files)
and `files.json` (the single files of the packs picked from a repository at a fixed commit, each pinned by its git blob
sha1, or by sha256 for the hand-picked sound effects). The SFZ files Rostrum generated (the studio kit, the drum kit's GM
map, the acoustic guitar's program) ship in `library_data/packs/sfz/<pack>/` and are copied in at install.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from rostrum_core import RostrumError, codes, did_you_mean

DATA = Path(__file__).resolve().parent / "library_data" / "packs"


@lru_cache(maxsize=1)
def catalog() -> dict[str, dict]:
    return {p["id"]: p for p in json.loads((DATA / "catalog.json").read_text(encoding="utf-8"))["packs"]}


@lru_cache(maxsize=1)
def _files() -> dict[str, dict]:
    return json.loads((DATA / "files.json").read_text(encoding="utf-8"))


def pack(name: str, where: str = "packs") -> dict:
    if name not in catalog():
        raise RostrumError(codes.NOT_FOUND, where, f'pack "{name}"', "is not a sample pack",
                           accepted=list(catalog()), hint=did_you_mean(name, catalog()))
    return catalog()[name]


def names(group: str | None = None) -> list[str]:
    return [i for i, p in catalog().items() if group in (None, p["group"])]


def credit(name: str) -> str | None:
    """The line a CC-BY pack must be credited with (None for the CC0 packs)."""
    return catalog().get(name, {}).get("credit")


def files(name: str) -> list[dict]:
    """The single files of a file pack: {url, path (inside the pack folder), bytes, sha256 | gitSha1}."""
    spec = _files()[name]
    out = []
    for row in spec["files"]:
        base, src, digest = row[0], row[1], row[2]
        url = src if not base else spec["bases"][base] + "/".join(quote(s) for s in src.split("/"))
        path = row[4] if len(row) > 4 else (f"{base}/{src}" if spec.get("prefix_base") else src)
        out.append({"url": url, "path": path, "bytes": row[3],
                    ("sha256" if len(digest) == 64 else "gitSha1"): digest})
    return out


def generated(name: str) -> list[tuple[Path, str]]:
    """The SFZ files Rostrum made for this pack: (the copy in the repo, its path inside the pack folder)."""
    root = DATA / "sfz" / name
    return [(p, p.relative_to(root).as_posix()) for p in sorted(root.rglob("*")) if p.is_file()] if root.is_dir() else []
