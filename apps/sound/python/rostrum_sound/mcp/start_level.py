"""Each instrument's starting level: how loud the engine sets it at track volume 1 (so volume 1 = "as the engine
levelled it", and a track's `volume_db` is already against that start). The ONE place that reads it from the engine.

PLUG-IN POINT: the engine's `describe` answer is to carry `STARTING_LEVELS` = {instrument key: dB} (key as
roles.key() names it, e.g. "builtIn:piano", "kit:drums"; dB against the engine's reference level). Until the engine answers it,
everything here returns None and callers say nothing about starting levels."""
from __future__ import annotations

from .. import roles

STARTING_LEVELS = "startingLevelsDb"      # the field name in `describe`; change here only


def table(describe: dict) -> dict:
    return describe.get(STARTING_LEVELS) or {}


def of(describe: dict, spec: dict | None):
    """The starting level (dB) of the instrument `spec`, or None when the engine does not say."""
    k = roles.key(spec) if spec else None
    v = table(describe).get(k)
    return round(v, 1) if isinstance(v, (int, float)) else None


def words(volume_db, start_db) -> str:
    """"+6.8 dB over its start" for a track's volume; with the start known, where it lands: "(start -21.0, now -14.2 dB)"."""
    if volume_db is None:
        return ""
    over = f"{volume_db:+.1f} dB from its starting level"
    return over + (f" ({start_db:+.1f} → {start_db + volume_db:+.1f} dB)" if start_db is not None else "")
