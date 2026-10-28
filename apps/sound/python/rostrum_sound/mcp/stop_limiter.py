"""The render's limiter, read for the listening check only when an asked stop could be flattened by it.

A stop the master limiter pulls 3 dB or more cannot land hard (round 2's jazz stop: 8.7 dB from the ride's peaks).
Naming the track that drives the limiter needs the stems (listen/limiter.py, the same reading look_sound uses), so it is
read only when the render limited that much and a stop was asked; otherwise the check runs without it."""
from __future__ import annotations

from rostrum_core import RostrumError

from .. import fit_loudness as fit
from ..listen.limiter import limiter
from ..listen.stop_soft import HARD_DB
from .tools_look import _limiter_inputs


def read(ctx, doc, r: dict, moments) -> tuple[dict | None, str | None]:
    """-> (listen.limiter's result or None, the most peaked track of the render or None)."""
    peaky = fit.peakiest_track(r) if r.get("tracks") else None
    hard = ((r.get("master") or {}).get("limiterMaxReductionDb") or 0) >= HARD_DB
    if not (hard and any(m.get("kind") == "stop" for m in moments)):
        return None, peaky
    lim = _limiter_inputs(ctx, doc)
    if not lim:
        return None, peaky
    try:
        return limiter(lim["stems"], lim["reduction"], lim["caveat"], engine_max_db=lim["engine_max_db"], max_limit_db=lim["max_limit_db"]), peaky
    except RostrumError:            # a stem the ears cannot read: the stop is still checked, without the drivers
        return None, peaky
