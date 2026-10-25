"""A voice line's takes: the seeds whose audio is already in the cache (DESIGN.md §3.11 step 4). The document holds only
the line's current `seed`; the cache holds every take that was made, so "Speak again" is `line.set {seed: newest + 1}`
and the ◂ ▸ arrows are `line.set {seed: the neighbouring made take}` (instant: the audio is already there). No Qt."""
from __future__ import annotations

from rostrum_sound import voice_lines

SEARCH = 20          # the seeds looked at (a line is not re-spoken more than that many times)


def made(track: dict, line: dict) -> list[int]:
    """The seeds of this line's made takes (audio in the cache), in order."""
    return [s for s in range(1, SEARCH + 1) if voice_lines.take_of(track, {**line, "seed": s}) is not None]


def fresh_seed(track: dict, line: dict) -> int:
    """The seed for "Speak again": one past the newest take (and past the current seed, made or not)."""
    return max([*made(track, line), int(line.get("seed", 1))]) + 1


def neighbour(track: dict, line: dict, step: int):
    """The seed of the made take `step` (-1 / +1) away from the line's current one, or None at the end."""
    have, now = made(track, line), int(line.get("seed", 1))
    at = have.index(now) if now in have else None
    return have[at + step] if at is not None and 0 <= at + step < len(have) else None


def label(track: dict, line: dict) -> str:
    """"Take 2 of 3" once the line has more than one take, else ""."""
    have, now = made(track, line), int(line.get("seed", 1))
    return f"Take {have.index(now) + 1} of {len(have)}" if len(have) > 1 and now in have else ""


def mark_takes(rows: list[dict], root: dict) -> None:
    """The take is named on the block ("Take 2 of 3 · words") for lines with more than one, and the block says which
    way a take is left (`canBack` / `canNext`): the lane draws its ◂ ▸ arrows from that (TakeArrows.qml)."""
    by_id = {ln["id"]: (t, ln) for t in root.get("tracks", []) if t.get("instrument") == "voice" for ln in t.get("lines", [])}
    if not by_id:               # no voice lines in the song: no pass over every block of the rows
        return
    for r in rows:
        for b in r.get("blocks", []):
            if b["type"] == "line" and b["id"] in by_id:
                name = label(*by_id[b["id"]])
                if name:
                    b["label"] = f"{name} · {b['label']}"
                    b["canBack"] = neighbour(*by_id[b["id"]], -1) is not None
                    b["canNext"] = neighbour(*by_id[b["id"]], 1) is not None
