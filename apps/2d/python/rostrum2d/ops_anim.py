"""2D's animation and key-timing operations (anim.ease, key.scale, key.paste, key.stagger: rostrum_core.keys.anim_ops)
with 2D's setting names (anims.py) and time: a layer's own seconds sit in its composition through its start and its
groups (retime.py), a key on a shared marker is placed through the project's markers, key.stagger moves a layer's keys
together and orders layers by the layers list or where they are seen (ops_stagger.py).
"""
from __future__ import annotations

from rostrum_core.keys import marked
from rostrum_core.keys.anim_ops import Timing, register_anim_ops
from rostrum_core.marker_times import seconds
from rostrum_core.tree import index

from . import fields as F
from .anims import NAMES
from .kind import REGISTRY as R
from .ops_keys import put_key
from .ops_stagger import CASCADE
from .ops_timing import _times
from .retime import offset_of


def _own_seconds(ctx, key: dict, owner_id: str) -> float:
    """A key's time in its owner's own seconds (a marker key placed through the project's markers)."""
    if not marked.marked(key):
        return float(key["t"])
    return seconds(key["t"], _times(ctx), key["id"]) - offset_of(ctx.doc, owner_id, _times(ctx))


def _layer_of(ctx, key_id: str) -> str:
    idx = index(ctx.doc, ctx.kind.lists)
    loc = idx[key_id]
    while loc.parent is not None and idx[loc.parent].item["type"] not in F.LAYERS:
        loc = idx[loc.parent]
    return loc.parent


register_anim_ops(R, owners=F.ANIMATED_OWNERS, put_key=put_key, names=NAMES, orders=CASCADE,
                  timing=Timing(own_seconds=_own_seconds, offset=lambda ctx, oid: offset_of(ctx.doc, oid, _times(ctx)),
                                group_of=_layer_of))
