"""Keys, shared by every app: the easing table, the evaluator, the key fields table and the four generic key
operations (`register_key_ops`). See ../../README.md › Keys."""
from .easing import BEZIERS, NAMES as EASES, ease
from .evaluate import animated, key_value, keys_of, mix_color, track_value
from .fields import KEY_FIELDS
from .ops import key_id, register_key_ops

__all__ = ["BEZIERS", "EASES", "KEY_FIELDS", "animated", "ease", "key_id", "key_value", "keys_of", "mix_color",
           "register_key_ops", "track_value"]
