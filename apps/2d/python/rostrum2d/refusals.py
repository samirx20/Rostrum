"""States the engine can't draw, refused when they are set (an operation's change), never first at preview or export:
a morph between shapes with different piece counts, and per-letter animation of a text wrapped in a box.
`problems(item)` is called by kind.check for every changed item, so a saved file never holds them."""
from __future__ import annotations

from . import pathdata


def _pieces(d: str) -> int | None:
    try:
        return sum(1 for c in pathdata.commands(d) if c[0] == "M")
    except ValueError:
        return None                             # a bad `d` has its own message (kind._check_keys)


def problems(item: dict) -> list[str]:
    out = []
    counts = {}
    for k in item.get("keys", []):
        if k.get("prop") == "d" and "d" in k and (n := _pieces(k["d"])) is not None:
            counts[k.get("t")] = n
    if len(set(counts.values())) > 1:
        shown = ", ".join(f"{n} at {t} s" for t, n in sorted(counts.items(), key=lambda kv: kv[0] or 0))
        out.append(f'{item["id"]}.d: a morph needs the same number of pieces (subpaths) in every key; the keys have {shown}')
    if item.get("type") == "text" and item.get("boxWidth", 0) and (item.get("letterDelay", 0) or item.get("path")):
        out.append(f'{item["id"]}.boxWidth: text wrapped in a box is not animated letter by letter yet '
                   f"(set boxWidth to 0, or turn letter delay off and clear the path)")
    return out
