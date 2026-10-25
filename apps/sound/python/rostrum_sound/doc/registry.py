"""The Sound document's one operation list, the table of where its items live, and two helpers every
`ops_*` module uses. The operations register themselves on import (see `kind.py`)."""
from __future__ import annotations

from rostrum_core import Registry
from rostrum_core.tree import index

REGISTRY = Registry()

# Where child items live, per item type (shared/core tree.py).
LISTS = {
    "doc": ["tracks", "buses", "markers", "master", "tempos", "meters", "keys", "sections"],
    "track": ["notes", "hits", "clips", "lines", "effects", "automation", "sends", "ducks"],
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


def taken(ctx):
    """Every id in the working document (new ids must not collide): the call's own index (rostrum_core.run.Context,
    kept up to date by every edit of the call). Indexing the song again walked all of it for each note or hit added
    (~3 ms a drum hit on the critic's song, growing with it)."""
    idx = getattr(ctx, "idx", None)
    return idx.keys() if idx is not None else set(index(ctx.doc, LISTS))
