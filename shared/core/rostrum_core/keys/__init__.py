"""Keys, shared by every app: the easing table, the evaluator, the key fields table and the four generic key
operations (`register_key_ops`), the animation reading (anims.py) and the operations on whole animations and key timing
(`register_anim_ops`: anim.ease, key.scale, key.paste, key.stagger). See ../../README.md › Keys."""
from . import after
from .easing import BEZIERS, NAMES as EASES, ease
from .evaluate import animated, key_value, keys_of, mix_color, track_value
from . import marked
from .fields import KEY_FIELDS
from . import spring as springs
from .ops import key_id, register_key_ops
from .anims import Names, animations
from .anim_ops import Timing, register_anim_ops
from .stagger import Orders

__all__ = ["BEZIERS", "after", "EASES", "KEY_FIELDS", "animated", "ease", "key_id", "key_value", "keys_of", "marked", "mix_color",
           "register_key_ops", "springs", "track_value", "Names", "animations", "Timing", "register_anim_ops", "Orders"]
