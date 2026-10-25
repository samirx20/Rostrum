"""The Library drawer's search (UX_SPEC 3.13): typed words narrow every section by name, live. One place decides what
matches, so the drawer's lists, "Nothing called …" and Enter's top result all agree. Plain data in, plain data out (no Qt).

    narrow("sky", sections)      # {section: [entries whose words all appear in their name]} (a section may be empty)
    top(found)                   # the first entry shown, as (section, entry): what Enter uses
"""
from __future__ import annotations

from pathlib import Path

SECTIONS = ("colors", "textStyles", "logos", "paintings", "docStyles")      # the drawer's order, top to bottom
MORE_THAN = 12                                                              # the search box shows from this many things up


def _words(section: str, e: dict) -> str:
    """What a typed word may match: a colour by name and hex, a logo by name and file name, the rest by name."""
    extra = {"colors": e.get("value", ""), "logos": Path(e.get("file", "")).name}.get(section, "")
    return f'{e.get("name", "")} {extra}'.lower()


def narrow(query: str, sections: dict[str, list]) -> dict[str, list]:
    """Every section cut to the entries that have all the typed words (an empty query keeps everything)."""
    ws = query.lower().split()
    return {s: [e for e in es if all(w in _words(s, e) for w in ws)] for s, es in sections.items()}


def key(section: str, e: dict) -> str:
    """One row's name in the drawer's `shown` list."""
    return f'{section}:{e.get("id") or e.get("name", "")}'


def top(found: dict[str, list]) -> tuple[str, dict] | None:
    """The first thing shown, in the drawer's order: (section, entry), or None when nothing matched."""
    return next(((s, found[s][0]) for s in SECTIONS if found.get(s)), None)


def count(sections: dict[str, list]) -> int:
    return sum(len(es) for es in sections.values())
