"""3D's animation and key-timing operations: anim.ease (ease whole stretches in one change), key.scale (stretch or
squeeze keys in time), key.paste (copies of keys onto the same settings of other items) and key.stagger (several items'
keys one after another), from rostrum_core.keys.anim_ops, with 3D's setting names (anims.py: Position, Turn and Scale
each one setting). Times are document seconds, as key.add's `t`. The timeline's animation panel calls the same ones.
"""
from __future__ import annotations

from rostrum_core.keys.anim_ops import register_anim_ops

from . import fields as F
from .anims import NAMES
from .kind import REGISTRY as R
from .ops_keys import put_key

register_anim_ops(R, owners=F.KEYED, put_key=put_key, names=NAMES)
