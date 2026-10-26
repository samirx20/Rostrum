"""look_motion's findings as a short list: identical findings (120 windows entering together, 26 motes ...) are one line
with a count and examples, the ones that matter first, capped with a note on how to ask for the rest."""
from __future__ import annotations

import re

LIMIT = 20          # lines of each kind (layers, findings) a reply lists before "N more"
_ORDER = {"never_shown": 0, "not_showing": 1, "key_after_end": 2, "key_does_nothing": 3, "nothing_moves": 4, "entrances_overlap": 5}


def stem(name: str) -> str:
    """mote_12 -> mote_# : layers made in a loop share one."""
    return re.sub(r"\d+", "#", name)


def _key(f: dict) -> tuple:
    kind = f["kind"]
    if kind == "entrances_overlap":
        return kind, tuple(sorted(stem(i) for i in f["layers"]))
    if kind in ("never_shown", "not_showing"):
        return kind, stem(f["layer"]), tuple(f.get("reasons", ())), f.get("why", "")
    if kind in ("key_after_end", "key_does_nothing"):
        return kind, stem(f["owner"]), f["field"]
    return kind, f["text"]


def _who(f: dict) -> list[str]:
    return f.get("layers") or [f.get("layer") or f.get("owner", "")]


def _examples(ids: list[str], n: int = 3) -> str:
    return ", ".join(ids[:n]) + (" …" if len(ids) > n else "")


def _text(kind: str, members: list[dict]) -> str:
    first, n = members[0], len(members)
    if kind == "entrances_overlap":
        secs = [m["overlap_s"] for m in members]
        together = sum(1 for m in members if m["apart_s"] < 0.001)
        pairs = _examples([f'{m["layers"][0]} + {m["layers"][1]}' for m in members])
        return (f'{n} pairs of layers move at the same time ({pairs}): overlapping {min(secs)}–{max(secs)} s, '
                f'{together} starting together.')
    ids = sorted({i for m in members for i in _who(m)})
    if kind == "never_shown":
        return f'{len(ids)} layers ({_examples(ids)}) are never on screen: {first["why"]}.'
    if kind == "not_showing":
        return f'{len(ids)} layers ({_examples(ids)}) are not on screen at {first["at"]} s: {", ".join(first["reasons"])}.'
    return f'{len(ids)} layers ({_examples(ids)}): {first["text"]}'


def grouped(findings: list[dict]) -> list[dict]:
    """One finding per group of identical ones (a single one stays as it was), the ones that matter first, then the biggest group."""
    groups: dict[tuple, list[dict]] = {}
    for f in findings:
        groups.setdefault(_key(f), []).append(f)
    out = []
    for members in groups.values():
        kind = members[0]["kind"]
        out.append(members[0] if len(members) == 1 else {"kind": kind, "text": _text(kind, members), "count": len(members),
                   "layers": sorted({i for m in members for i in _who(m)})[:10]})
    return sorted(out, key=lambda g: (_ORDER.get(g["kind"], 9), -g.get("count", 1)))


def capped(groups: list[dict], limit: int) -> tuple[list[dict], str]:
    """The first `limit` groups and the sentence about the rest ("" when none left out)."""
    if len(groups) <= limit:
        return groups, ""
    left = groups[limit:]
    items = sum(g.get("count", 1) for g in left)
    return groups[:limit], (f"{len(left)} more finding line{'s' * (len(left) != 1)} ({items} findings) not listed: "
                            "ask with `all: true`, a bigger `limit`, or `layers` for the ones you are tuning.")
