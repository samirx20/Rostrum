"""The one place an editable mesh's per-face and per-edge data follow a topology edit (SPEC §4.3): every operation
that adds, splits or removes faces hands its poly.Change here, and gets back the item fields to set.

- `faceMaterials`: a split face keeps its parent's material, a new wall the face it grew from; "" when it has none.
  All "" is stored as the empty list (every face the item's).
- `creases`: an edge still there stays sharp; a cut or moved edge's pieces (Change.chains) stay sharp; an edge that is
  gone (bevelled away) is dropped.
- Points no face uses any more are removed, and faces and creases renumbered to match.
"""
from __future__ import annotations

from .poly import Change, pack


def edge_set(faces) -> set[tuple[int, int]]:
    return {(min(a, b), max(a, b)) for f in faces for a, b in zip(f, f[1:] + f[:1])}


def crease_pairs(item: dict) -> list[tuple[int, int]]:
    flat = list(item.get("creases") or [])
    return sorted({(min(a, b), max(a, b)) for a, b in zip(flat[0::2], flat[1::2])})


def flat(pairs) -> list[int]:
    return [int(v) for e in sorted(pairs) for v in e]


def materials(item: dict, parents: list[int]) -> list[str]:
    old = list(item.get("faceMaterials") or [])
    if not old:
        return []
    if len(old) != len(item.get("faceCounts", [])):
        raise ValueError(f"faceMaterials has {len(old)} entries for {len(item['faceCounts'])} faces; "
                         "set it to [] or one material id per face")
    out = [old[p] if p >= 0 else "" for p in parents]
    return out if any(out) else []


def apply(item: dict, ch: Change) -> dict:
    """The item fields after the change: points, faceCounts, faceIndices, faceMaterials, creases."""
    if len(ch.parents) != len(ch.faces):
        raise ValueError(f"internal: {len(ch.parents)} face parents for {len(ch.faces)} faces")
    now = edge_set(ch.faces)
    sharp = set()
    for e in crease_pairs(item):
        if e in now:
            sharp.add(e)
        elif e in ch.chains:
            c = ch.chains[e]
            sharp |= {(min(a, b), max(a, b)) for a, b in zip(c, c[1:])} & now
    used = sorted({v for f in ch.faces for v in f})
    new = {v: n for n, v in enumerate(used)}
    faces = [[new[v] for v in f] for f in ch.faces]
    out = pack([ch.points[v] for v in used], faces)
    out["faceMaterials"] = materials(item, ch.parents)
    out["creases"] = flat({(min(new[a], new[b]), max(new[a], new[b])) for a, b in sharp})
    return out
