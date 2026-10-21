"""A plug-in's settings as the generic inspector rows (no Qt): built from the parameter list the engine scan gave
(`engine.plugins()`), the first few on screen and the rest behind More, so no plug-in has a hand-made panel.

The values come from the document's `plugin` record (`params` holds only what was changed; the plug-in's own
default shows for the rest). A setting with a lane (a list of [time, value]) shows its first value, key mark filled.
"""
from __future__ import annotations

from types import SimpleNamespace

from rostrum_core import Param
from rostrum_gui import rows
from rostrum_sound.doc import values as V

SHOWN = 6          # settings on screen before More (the scan lists a plug-in's most important first)


def layout(params: list[dict]) -> list[dict]:
    """Static rows for a scanned parameter list [{id, name, min, max, default}]. Skipped: empty ranges and unused
    slots (a plug-in like Airwindows Consolidated names a slot its current effect doesn't use "-")."""
    ps = []
    used = (q for q in params if q.get("max", 0) > q.get("min", 0) and any(ch.isalnum() for ch in q.get("name", "x")))
    for p in used:
        ps.append(Param.number(str(p["id"]), min=p["min"], max=p["max"], step=V.step(p["min"], p["max"]),
                               default=p.get("default", p["min"]), label=p.get("name") or str(p["id"]), group="Settings",
                               importance="primary" if len(ps) < SHOWN else "deep"))
    return [r for r in rows.layout(SimpleNamespace(params=ps)) if r["row"] != "group"]


def values(spec: dict) -> dict:
    """The record's settings as plain numbers (a lane shows its first value)."""
    return {k: (v[0][1] if v else 0) if isinstance(v, list) else v for k, v in (spec.get("params") or {}).items()}


def evaluate(static: list[dict], spec: dict, more_open: bool) -> list[dict]:
    lanes = {k for k, v in (spec.get("params") or {}).items() if isinstance(v, list)}
    return rows.evaluate(static, values(spec), {}, more_open, lambda n: "keyed" if n in lanes else "")


def with_param(spec: dict, param_id: str, value) -> dict:
    """The record with one setting changed (the whole record is what the one operation writes)."""
    return {**spec, "params": {**(spec.get("params") or {}), param_id: value}}


def after_window(spec: dict, answer: dict) -> dict:
    """The record after the plug-in's own window closed: its state and settings; a setting that has a lane keeps it."""
    old, got = spec.get("params") or {}, answer.get("params") or {}
    if isinstance(got, list):    # [{id, value}] or {id: value}
        got = {str(p["id"]): p["value"] for p in got}
    params = {k: old[k] if isinstance(old.get(k), list) else v for k, v in got.items()}
    out = {**spec, "params": {**old, **params}}
    if answer.get("state"):
        out["state"] = answer["state"]
    return out
