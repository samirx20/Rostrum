"""Icons by name: the SVG text of a Lucide (ISC) or Tabler (MIT) icon, as agents name them in web code.

    icon("arrow-right")                 Lucide's, else Tabler's
    icon("tabler:arrow-right")          one set (also "lucide-…", "ti-…", "icon-tabler-…", "i-lucide-…")
    icon("ArrowRight") / icon("IconHeart") / icon("Trash2")   the React component names
    icon("heart", color="#fff", size=48, stroke_width=1.5)

`color` replaces `currentColor` (the sets colour themselves with it); without it the icon keeps `currentColor`.
Tabler's filled icons are "<name>-filled". Each set is one zip in data/ (tools/assets/pack_icons.py made it).
"""
from __future__ import annotations

import difflib
import json
import re
import zipfile
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).with_name("data")
ORDER = ("lucide", "tabler")
_PREFIXES = (("i-lucide-", "lucide"), ("lucide-", "lucide"), ("i-tabler-", "tabler"), ("icon-tabler-", "tabler"),
             ("tabler-", "tabler"), ("ti ti-", "tabler"), ("ti-", "tabler"))


class IconNotFound(LookupError):
    """No icon of that name; the message names the five nearest."""


def _zip(kind: str) -> Path:
    found = sorted(DATA.glob(f"{kind}-*.zip"))
    if not found:
        raise FileNotFoundError(f"the {kind} icons are not installed ({DATA})")
    return found[-1]


@lru_cache(maxsize=None)
def _set(kind: str) -> dict[str, str]:
    with zipfile.ZipFile(_zip(kind)) as z:
        return json.loads(z.read("icons.json"))


def icon_sets() -> dict[str, str]:
    """{set: version} of the sets that ship, e.g. {"lucide": "1.65.0", "tabler": "3.50.0"}."""
    return {k: _zip(k).stem.split("-", 1)[1] for k in ORDER}


def icon_names(kind: str | None = None) -> list[str]:
    """Every icon name of one set, or of both as "set:name"."""
    if kind:
        return sorted(_set(kind))
    return [f"{k}:{n}" for k in ORDER for n in sorted(_set(k))]


def _kebab(name: str) -> str:
    """React's ArrowRight / Trash2 / IconHeartFilled -> arrow-right / trash-2 / heart-filled (other names as written)."""
    if not re.fullmatch(r"[A-Z][A-Za-z0-9]*", name):
        return name.strip().lower().replace("_", "-").replace(" ", "-")
    name = re.sub(r"^Lucide(?=[A-Z])|(?<=[a-z0-9])Icon$", "", name)
    return re.sub(r"(?<=[a-z])(?=[A-Z0-9])|(?<=[0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", "-", name).lower()


def _parse(name: str) -> tuple[tuple[str, ...], list[str]]:
    """(the sets to look in, the names to try in each)."""
    raw = name.strip()
    sets = ORDER
    if ":" in raw:
        prefix, raw = raw.split(":", 1)
        sets = (prefix.strip().lower(),)
    else:
        for prefix, kind in _PREFIXES:
            if raw.lower().startswith(prefix):
                sets, raw = (kind,), raw[len(prefix):]
                break
    tries = [_kebab(raw)]
    if re.fullmatch(r"Icon[A-Z][A-Za-z0-9]*", raw):          # Tabler's React names: IconArrowRight
        tries.append(_kebab(raw[4:]))
    return sets, tries


def _svg(text: str, color: str | None, size: float | None, stroke_width: float | None) -> str:
    if color is not None:
        text = text.replace("currentColor", color)
    if size is not None:
        text = re.sub(r'(<svg[^>]*?) width="[^"]*" height="[^"]*"', rf'\1 width="{size:g}" height="{size:g}"', text, count=1)
    if stroke_width is not None:
        text = re.sub(r'(<svg[^>]*?) stroke-width="[^"]*"', rf'\1 stroke-width="{stroke_width:g}"', text, count=1)
    return text


def icon(name: str, color: str | None = None, size: float | None = None, stroke_width: float | None = None) -> str:
    """The icon's SVG text (24×24 viewBox). A name no set has raises IconNotFound naming the five nearest."""
    sets, tries = _parse(name)
    unknown = [k for k in sets if k not in ORDER]
    if unknown:
        raise IconNotFound(f'no icon set "{unknown[0]}"; the sets are {", ".join(ORDER)}')
    for kind in sets:
        for n in tries:
            if n in _set(kind):
                return _svg(_set(kind)[n], color, size, stroke_width)
    shown = {}                                              # bare name -> as the agent would write it
    for k in reversed(sets):
        shown.update({n: n if k == sets[0] else f"{k}:{n}" for n in _set(k)})
    near = [shown[n] for n in difflib.get_close_matches(tries[0], list(shown), n=5, cutoff=0.0)]
    where = f"the {sets[0]} icons" if len(sets) == 1 else "Lucide or Tabler"
    raise IconNotFound(f'no icon "{name}" in {where}; nearest: {", ".join(near)}')
