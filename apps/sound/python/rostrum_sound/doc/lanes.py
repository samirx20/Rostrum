"""Every value that can change over time, in one place: which lanes an item offers, each lane's range, and where
its points live.

Two homes, one view. A mix value (a track's volume, pan, expression; a bus' or the master's volume and pan; a
send's level) is an `automation` child of its item. An effect setting that takes an envelope (a compressor's
threshold, a reverb's mix, a delay's feedback …) and a plug-in's parameter ("param:<id>") keep their points in the
setting itself, the form the engine reads. `automation.set` writes both, so a person's lane drag and an agent's
call are the same operation, one history step.
"""
from __future__ import annotations

from .. import names
from . import effects as FX

MIX = {"track": names.TRACK_LANES, "master": names.MASTER_LANES, "bus": names.BUS_LANES, "send": names.SEND_LANES}
MIX_RANGE = {"volume": (0, 4), "pan": (-1, 1), "level": (0, 4), "dynamics": (0, 2), "vibrato": (0, 1)}
PARAM = "param:"
TARGETS = (*MIX, "effect")


def _plugin_params(item: dict) -> dict:
    return (item.get("plugin") or {}).get("params", {}) or {}


def offered(item: dict) -> list[str]:
    """The lanes this item has: mix values, an effect's envelope settings, a plug-in's changed parameters
    (any other "param:<id>" is accepted too; see `accepts`)."""
    if item.get("type") == "effect":
        if item["effect"] == "plugin":
            return [PARAM + k for k in _plugin_params(item)]
        return [n for n, s in FX.EFFECTS[item["effect"]].items() if s.env]
    return list(MIX.get(item.get("type"), []))


def accepts(item: dict, lane: str) -> bool:
    if item.get("type") == "effect" and item.get("effect") == "plugin":
        return lane.startswith(PARAM) and len(lane) > len(PARAM)
    return lane in offered(item)


def range_of(item: dict, lane: str) -> tuple[float, float] | None:
    """(lo, hi) of the lane's values; None for a plug-in parameter (its range is the plug-in's, from the scan)."""
    if item.get("type") != "effect":
        return MIX_RANGE.get(lane)
    if lane.startswith(PARAM):
        return None
    s = FX.EFFECTS[item["effect"]][lane]
    return (s.lo, s.hi)


def held(item: dict, lane: str):
    """The stored value of an effect lane: a number, an envelope, or None (the default applies)."""
    if lane.startswith(PARAM):
        return _plugin_params(item).get(lane[len(PARAM):])
    return item.get(lane)


def points(item: dict, lane: str) -> list[list]:
    """The lane's points as stored ([time, value], times in whatever form they were written); [] when it has none."""
    if item.get("type") == "effect":
        v = held(item, lane)
        return [list(p) for p in v] if isinstance(v, list) else []
    return next(([list(p) for p in a.get("points", [])] for a in item.get("automation", []) if a["lane"] == lane), [])


def base(item: dict, lane: str) -> float | None:
    """The item's own steady setting for the lane (the line a lane with no points shows)."""
    if item.get("type") == "effect":
        v = held(item, lane)
        if v is None and not lane.startswith(PARAM):
            v = FX.EFFECTS[item["effect"]][lane].default
    else:
        v = item.get(lane)
    return float(v) if isinstance(v, (int, float)) and not isinstance(v, bool) else None


def effect_value(item: dict, lane: str, pts: list[list]):
    """What `automation.set` writes into an effect for `pts`: the effect field's new value (or, for a plug-in,
    its whole new `plugin` record). An emptied lane keeps the sound it started with: its first point's value."""
    old = points(item, lane)
    value = pts if pts else (old[0][1] if old else held(item, lane))
    if not lane.startswith(PARAM):
        return lane, value
    rec = dict(item.get("plugin") or {})
    params = {**_plugin_params(item)}
    if value is None:
        params.pop(lane[len(PARAM):], None)
    else:
        params[lane[len(PARAM):]] = value
    return "plugin", {**rec, "params": params}
