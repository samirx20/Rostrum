"""Stems by group (`render_mix {stems: "groups"}`, the Export sheet's "a stem per group"): one stem per group (a bus
that tracks play into) and one per track that plays straight to the master (an ungrouped track). A track inside a
group is inside its group's stem, so its own stem is not delivered; a group inside another group is inside that one.

The engine already writes both (ENGINE_CONTRACT.md: every track's stem, a `<bus>.bus.wav` per bus, `direct` = the tracks
that play to the master; the direct tracks' stems plus the top-level bus stems add up to the mix before the master
bus), so nothing is combined here: the render asks for everything and `keep` leaves out what a group already holds.
"""
from __future__ import annotations

from pathlib import Path

from . import names


def routed_to_master(item: dict) -> bool:
    return item.get("output", names.MASTER_OUT) == names.MASTER_OUT


def keep(r: dict, root: dict) -> dict:
    """The engine's answer `r` with only the group stems and the ungrouped tracks' stems (the other files deleted)."""
    buses = {b["id"] for b in root.get("buses", []) if routed_to_master(b)}
    direct = set(r["direct"]) if r.get("direct") is not None else {t["id"] for t in root.get("tracks", []) if routed_to_master(t)}
    stems = {k: p for k, p in (r.get("stems") or {}).items() if k in direct}
    bus_stems = {k: p for k, p in (r.get("busStems") or {}).items() if k in buses}
    for p in [p for k, p in (r.get("stems") or {}).items() if k not in stems] + \
             [p for k, p in (r.get("busStems") or {}).items() if k not in bus_stems]:
        Path(p).unlink(missing_ok=True)
    return {**r, "stems": stems, "busStems": bus_stems, "stemsBy": "groups"}
