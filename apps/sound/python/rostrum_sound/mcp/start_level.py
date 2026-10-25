"""Each instrument's starting level: the gain the compiler puts under its track's volume (doc/preset_level.py, so
volume 1 = "as levelled", and a track's `volume_db` is already against that start). Keys as roles.key() names them:
"builtIn:piano", "kit:drums"."""
from __future__ import annotations

from .. import roles
from ..doc.preset_level import starting_levels_db


def table(describe: dict | None = None) -> dict:
    return starting_levels_db()


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
