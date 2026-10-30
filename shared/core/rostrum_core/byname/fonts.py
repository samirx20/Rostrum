"""Any Google Fonts family by name: its font files, fetched once from github.com/google/fonts (the commit the family
list in data/google-fonts.json was made from, so the names and files always match) into the shared cache and kept.

    font_files("Inter")                                   every face (variable families: one or two files)
    font_files("Playfair Display", weights=[700], italic=True)    only what CSS asks for (static families)
    google_family("playfair-display") -> "Playfair Display"       names as agents write them; None if not a family

Only OFL and Apache families are listed. A name that isn't a family raises FontNotFound naming the five nearest;
offline with the files not fetched yet raises FontNeedsInternet, one plain line.
"""
from __future__ import annotations

import difflib
import json
import re
import threading
from functools import lru_cache
from pathlib import Path

from . import net
from ..cache import CACHE

KIND = "google-fonts"
_lock = threading.Lock()


class FontNotFound(LookupError):
    """No Google Fonts family of that name; the message names the five nearest."""


class FontNeedsInternet(OSError):
    """The family is known but its files aren't fetched yet and the internet can't be reached."""


@lru_cache(maxsize=1)
def _catalogue() -> dict:
    return json.loads(Path(__file__).with_name("data").joinpath("google-fonts.json").read_text("utf-8"))


def google_families() -> list[str]:
    return list(_catalogue()["families"])


def _key(name: str) -> str:
    return re.sub(r"[^a-z0-9]", "", name.lower())


@lru_cache(maxsize=1)
def _by_key() -> dict[str, str]:
    return {_key(f): f for f in _catalogue()["families"]}


def google_family(name: str) -> str | None:
    """The family's exact name for any spelling agents use ("inter", "Playfair+Display", "playfair-display"), or None."""
    return _by_key().get(_key(name.replace("+", " ").strip().strip("'\"")))


def _family(name: str) -> str:
    family = google_family(name)
    if family is None:
        near = difflib.get_close_matches(name.strip().strip("'\""), google_families(), n=5, cutoff=0.0)
        raise FontNotFound(f'"{name}" is not a Google Fonts family; nearest: {", ".join(near)}')
    return family


def _url(family: str, file: str) -> str:
    sha = _catalogue()["source"].rsplit("@", 1)[1]
    return f"https://raw.githubusercontent.com/google/fonts/{sha}/{_catalogue()['families'][family]}/{file}"


def _fetched(family: str, file: str) -> Path:
    """One file of the family, from the cache, else fetched into it (a whole file or nothing)."""
    key = f"{_catalogue()['families'][family].split('/')[1]}--{re.sub(r'[^A-Za-z0-9.,_-]', '_', file)}"
    with _lock:
        folder = CACHE.get(KIND, key)
        if folder is None:
            try:
                data = net.get(_url(family, file))
            except OSError as e:
                raise FontNeedsInternet(f'the font "{family}" is fetched from the internet the first time it is used, '
                                        f"and the internet can't be reached ({e})") from None
            folder = CACHE.put(KIND, key, lambda tmp: (tmp / file).write_bytes(data),
                               {"family": family, "file": file, "from": _url(family, file)})
    return folder / file


def faces(name: str) -> list[dict]:
    """The family's faces as its METADATA.pb lists them: [{file, italic, weight: (lo, hi)}] (variable: its wght range)."""
    family = _family(name)
    text = _fetched(family, "METADATA.pb").read_text("utf-8")
    axis = re.search(r'axes \{\s*tag: "wght"\s*min_value: ([\d.]+)\s*max_value: ([\d.]+)', text)
    out = []
    for block in re.findall(r"fonts \{(.*?)\n\}", text, flags=re.S):
        file = re.search(r'filename: "([^"]+)"', block).group(1)
        w = float(re.search(r"weight: (\d+)", block).group(1))
        weight = (float(axis.group(1)), float(axis.group(2))) if axis and "wght" in file else (w, w)
        out.append({"file": file, "italic": 'style: "italic"' in block, "weight": weight})
    return out


def _nearest(faces_: list[dict], w: float) -> dict:
    """CSS font matching's pick among faces of one slope (as the 2D engine's fonts.rs does)."""
    def rank(f):
        lo, hi = f["weight"]
        if lo <= w <= hi:
            return (0, 0.0)
        above, gap = (True, lo - w) if lo > w else (False, w - hi)
        if 400 <= w <= 500:
            return ((1 if lo <= 500 else 3) if above else 2, gap)
        return (2 if above else 1, gap) if w < 400 else (1 if above else 2, gap)
    return min(faces_, key=rank)


def font_files(name: str, weights=None, italic: bool | None = None) -> list[Path]:
    """The family's files on this computer (fetched the first time). `weights` (CSS numbers) and `italic` (True: only
    italic, False: only upright, None: both) choose the faces as CSS would; nothing given = every face."""
    chosen = faces(name)
    if italic is not None:
        slope = [f for f in chosen if f["italic"] == italic]
        chosen = slope or chosen                                  # no italic: CSS draws the upright (synthesised)
    if weights is not None:
        picks = []
        for w in weights:
            for slope in {f["italic"] for f in chosen}:
                pick = _nearest([f for f in chosen if f["italic"] == slope], float(w))
                if pick not in picks:
                    picks.append(pick)
        chosen = picks
    family = _family(name)
    return [_fetched(family, f["file"]) for f in chosen]
