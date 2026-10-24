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


def short_name(name: str, vendor: str = "") -> str:
    """A plug-in's name for small places (a chip): without its vendor's name in front ("Airwindows Consolidated"
    by Airwindows is "Consolidated"). The full name stays in the settings panel and the inspector."""
    n, v = (name or "").strip(), (vendor or "").strip()
    rest = n[len(v):].lstrip(" -_·:") if v and n.lower().startswith(v.lower()) else ""
    return rest or n


FORMATS = ("clap", "vst3")      # the best format first: a plug-in installed in several formats is listed once


def one_each(catalog: list[dict], kind: str, key) -> list[dict]:
    """[{id, label}] of the scanned plug-ins of this kind, one row per plug-in (same name and vendor) in its best
    format, listed by name: "Surge XT Effects", never "Surge XT Effects · CLAP" and again "· VST3"."""
    best: dict = {}
    for p in catalog:
        if p.get("kind") != kind:
            continue
        name = (p.get("name") or p["id"]).strip()
        rank = FORMATS.index(str(p["format"]).lower()) if str(p["format"]).lower() in FORMATS else len(FORMATS)
        k = (name.lower(), (p.get("vendor") or "").lower())
        if k not in best or rank < best[k][0]:
            best[k] = (rank, name, p)
    return sorted(({"id": key(p), "label": name} for _, name, p in best.values()), key=lambda r: r["label"].lower())


def has_name(param: dict) -> bool:
    """A real name: a plug-in like Airwindows Consolidated names a slot its current effect doesn't use "-"."""
    return any(ch.isalnum() for ch in str(param.get("name") or ""))


def is_bypass(param: dict) -> bool:
    """The plug-in's own bypass switch (our own bypass sits next to the settings): flagged by the scan, or named so."""
    return bool(param.get("bypass") or param.get("isBypass")) or str(param.get("name") or "").strip().lower() == "bypass"


def layout(params: list[dict]) -> list[dict]:
    """Static rows for a scanned parameter list [{id, name, min, max, default}]. Skipped: empty ranges, the
    plug-in's own bypass, and parameters with no real name (never shown as "-")."""
    ps = []
    used = (q for q in params if q.get("max", 0) > q.get("min", 0) and has_name(q) and not is_bypass(q))
    for p in used:
        ps.append(Param.number(str(p["id"]), min=p["min"], max=p["max"], step=V.step(p["min"], p["max"]),
                               default=p.get("default", p["min"]), label=p["name"], group="Settings",
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
