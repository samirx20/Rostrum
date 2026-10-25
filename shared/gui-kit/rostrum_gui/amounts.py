"""The amounts popover's rows (INTERACTION.md 1.2 point 5; Sound's SPEC "Base A"), built from the operation's own
parameters, never drawn by hand. An action names its amounts (`Action.amounts`): each a parameter name of the operations
its calls make (the first operation that has it gives its `Param`: label, unit, display, range, default, importance),
or a `Param` of the app's own for an amount that is a screen choice ("Along the key", Repeat's "Until"). Primary
parameters are the popover's rows; the others sit under "More" inside it. A name no operation of this call has is
absent (Quantise's "Snap the ends too" on drum hits alone), and so is any row the app's `fit` marks not valid now.

The rows are the kit's settings rows (rows.layout / rows.evaluate), so the popover draws them with InspectorRow: a
number gets a slider beside its box when its range is short (`SLIDER_SPAN`), a choice a picker, a toggle a switch.
A "seed" amount adds "Another take" (a new seed: the same amounts, another result). No Qt here.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

from rostrum_core import Param

from . import rows as R
from . import value_kinds

SLIDER_SPAN = 200          # a plain number with a range this short or shorter slides (ms 0…200, times 1…64, ±24)
AGAIN = "seed"             # the amount "Another take" renews
NOT_ROW = ("valid", "default", "said", "importance", "fresh")


def params(action, calls, registry, fit: dict) -> list[Param]:
    """The `Param` of each of the action's amounts that this call has (in the action's order), as popover rows:
    one group, no heading; secondary ones under More (the app's `fit` may say otherwise: an operation's secondary
    `times` is Repeat…'s first row)."""
    ops = [registry.get(op) for op in dict.fromkeys(c["op"] for c in calls)]
    out = []
    for a in action.amounts:
        p = a if isinstance(a, Param) else next((q for op in ops for q in op.params if q.name == a), None)
        if p is not None:
            imp = fit.get(p.name, {}).get("importance", p.importance)
            out.append(replace(p, group="", valid_when=None, required=False,
                               importance="primary" if imp == "primary" else "deep"))
    return out


def layout(found: list[Param]) -> list[dict]:
    rows = R.layout(SimpleNamespace(params=found))
    for r in rows:
        if r["row"] == "param" and r["type"] == "number" and not r["display"] and r["min"] is not None \
                and r["max"] is not None and r["max"] - r["min"] <= SLIDER_SPAN:
            r["control"] = "slider"
    return rows


def start(p: Param, said: dict):
    """An amount's first value: the app's starting `default` (fit), else the parameter's, else the plain start."""
    if "default" in said:
        return said["default"]
    if p.default is not None:
        return p.default
    if p.type == "number":
        return min(max(0, p.min if p.min is not None else 0), p.max if p.max is not None else 0)
    return False if p.type == "toggle" else (p.options[0] if p.options else "")


def values(found: list[Param], remembered: dict, fit: dict) -> dict:
    """The amounts kept last time, else each one's start; `fresh` in the app's say: always the start (Start a bar
    here… starts at the bar nearest the marker, whatever was kept for another marker)."""
    return {p.name: remembered[p.name] if p.name in remembered and not fit.get(p.name, {}).get("fresh")
            else start(p, fit.get(p.name, {})) for p in found}


def evaluate(static: list[dict], vals: dict, fit: dict, more_open: bool) -> list[dict]:
    """The rows for these amounts, with the app's say (`fit`) on each. A picked value no longer offered falls back to
    the first option (and `vals` follows)."""
    out = R.evaluate(static, vals, {}, more_open)
    for r in out:
        if r["row"] != "param":
            continue
        said = fit.get(r["id"], {})
        r.update({k: v for k, v in said.items() if k not in NOT_ROW})
        if said.get("valid") is False:
            r["valid"] = r["holds"] = False
        if r["type"] == "choice" and r["options"] and r["value"] not in [o["value"] for o in r["options"]]:
            r["value"] = vals[r["id"]] = r["options"][0]["value"]
        r["said"] = said.get("said", True)
    holds = {r["id"]: r["holds"] for r in out if r["row"] == "param"}
    for r in out:
        if r["row"] == "more":
            r["holds"] = r["valid"] = any(holds[m] for m in r["members"])
    return out


def shown(rows: list[dict]) -> dict:
    """{name: value} of the amounts that apply now (what the calls get: an absent row's value is left out)."""
    return {r["id"]: r["value"] for r in rows if r["row"] == "param" and r["holds"]}


def words(rows: list[dict]) -> str:
    """The amounts in words for the history and the message line: "15 ms, 8 %". The primary rows that apply, each as
    its field shows it (or the app's `said` words); a number at 0 (none of it), a switch, and a row the app marks
    `said: False` are left out."""
    out = []
    for r in rows:
        if r["row"] != "param" or not r["valid"] or r["importance"] == "deep" or not r.get("said", True):
            continue
        v = r["value"]
        if isinstance(r.get("said"), str):                  # the app's own words for it ("bar 9")
            out.append(r["said"])
        elif r["type"] == "choice":
            out.append(next((o["label"] for o in r["options"] if o["value"] == v), str(v)))
        elif r["type"] == "number" and v:
            if r["display"]:
                out.append(value_kinds.format(r["display"], v, r["step"] or 0.01))
            else:
                sign = "+" if (r["min"] or 0) < 0 and v > 0 else ""
                out.append((f"{sign}{v:g}" + (f" {r['unit']}" if r["unit"] else "")).replace("-", "−"))
    return ", ".join(out)
