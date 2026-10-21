"""The Sound document's one operation list, the table of where its items live, and two helpers every
`ops_*` module uses. The operations register themselves on import (see `kind.py`)."""
from __future__ import annotations

from rostrum_core import Registry
from rostrum_core.tree import index

REGISTRY = Registry()

# Where child items live, per item type (shared/core tree.py).
LISTS = {
    "doc": ["tracks", "buses", "markers", "master", "tempos", "keys", "sections"],
    "track": ["notes", "hits", "clips", "sounds", "lines", "effects", "automation", "sends", "ducks"],
    "bus": ["effects", "automation"],
    "send": ["automation"],
    "clip": ["effects"],
    "master": ["effects", "automation"],
}
MASTER_ID = "master"


def set_fields(ctx, targets, args):
    for t in targets:
        for k, v in args.items():
            ctx.set(t, k, v)


def taken(ctx) -> set:
    """Every id in the working document (new ids must not collide)."""
    return set(index(ctx.doc, LISTS))
