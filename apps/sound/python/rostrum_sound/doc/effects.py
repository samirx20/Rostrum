"""Effects: every type's fields, defaults and ranges (engine contract § Effects), and the Params built from them.

One table is the source: `effect.add` / `effect.set` params, the defaults a new effect gets, and the per-type
range check all read it. A field name shared by several types (threshold, mix, release …) is one Param that is
valid when the effect is any of those types; its tighter per-type range is checked by `problems()`.
Ranges beyond the contract's defaults are ours; the engine's `describe` is the authority (the lead checks).
"""
from __future__ import annotations

from typing import NamedTuple

from rostrum_core import Param

from .. import names
from . import values as V


class F(NamedTuple):
    default: object
    lo: float | None = None
    hi: float | None = None
    env: bool = False           # takes a number or an envelope [[time, value], …]
    unit: str = ""
    importance: str = "primary"


TOGGLE, SPACE, BANDS = "toggle", "space", "bands"
EFFECTS = {
    "eq": {"bands": F(BANDS)},
    "compressor": {"threshold": F(-18, -80, 0, True, "dB"), "ratio": F(3, 1, 30, True),
                   "attack": F(0.01, 0.0001, 1, unit="s", importance="secondary"),
                   "release": F(0.15, 0.001, 5, unit="s", importance="secondary"),
                   "makeup": F(0, -24, 36, True, "dB"), "knee": F(6, 0, 24, unit="dB", importance="deep")},
    "reverb": {"space": F(SPACE), "mix": F(0.25, 0, 1, True), "decay": F(None, 0.1, 30, unit="s"),
               "damping": F(None, 0, 1, importance="secondary"), "size": F(None, 0, 1)},
    "delay": {"time": F(0.375, 0.001, 4, unit="s"), "feedback": F(0.35, 0, 0.98, True), "mix": F(0.2, 0, 1, True),
              "pingPong": F(TOGGLE, importance="secondary"), "damp": F(0.3, 0, 1, importance="secondary")},
    "saturate": {"drive": F(0.3, 0, 1, True), "mix": F(1, 0, 1, True)},
    "tape": {"wow": F(0.2, 0, 1, True), "flutter": F(0.2, 0, 1, True), "age": F(0.2, 0, 1, True)},
    "limiter": {"ceiling": F(-1, -24, 0, unit="dB"), "release": F(0.1, 0.001, 2, unit="s", importance="secondary")},
    "width": {"width": F(1, 0, 2, True), "monoBelow": F(120, 0, 1000, unit="Hz", importance="secondary")},
    "gate": {"threshold": F(-45, -100, 0, unit="dB"), "ratio": F(4, 1, 100), "range": F(30, 0, 100, unit="dB"),
             "attack": F(0.002, 0.0001, 1, unit="s", importance="secondary"),
             "hold": F(0.05, 0, 2, unit="s", importance="secondary"),
             "release": F(0.12, 0.001, 5, unit="s", importance="secondary")},
    "deess": {"freq": F(6000, 1000, 20000, unit="Hz"), "threshold": F(-30, -80, 0, unit="dB"),
              "range": F(8, 0, 40, unit="dB")},
    "dehum": {"freq": F(0, 0, 60, unit="Hz", importance="secondary"), "harmonics": F(6, 1, 16, importance="deep"),
              "width": F(40, 1, 200, importance="deep")},
}
TYPES = list(EFFECTS)
FREEVERB_ONLY = ("decay", "damping", "size")
IS = lambda name, value: {"is": [name, value]}  # noqa: E731

_band_params = [Param.choice("shape", names.EQ_SHAPES, required=True), V.env("freq", 20, 24000, required=True),
                V.env("gain", -36, 36), V.env("q", 0.1, 30)]
_band_rule, _band_schema = V.fields_of(_band_params, "band")


def _when(field_name, kind="effect"):
    types = [t for t, fs in EFFECTS.items() if field_name in fs]
    cond = IS(kind, types[0]) if len(types) == 1 else {"any": [IS(kind, t) for t in types]}
    if field_name in FREEVERB_ONLY:
        cond = {"all": [cond, {"any": [IS("space", s) for s in names.FREEVERB_SPACES]}]}
    return cond


def _param(field_name, specs, kind):
    first = specs[0]
    kw = dict(group="Effect", importance=first.importance, valid_when=_when(field_name, kind))
    if first.default == BANDS:
        return V.listof("bands", _band_rule, _band_schema, help="EQ bands: {shape, freq, gain, q}", **kw)
    if first.default == SPACE:
        return Param.choice("space", names.SPACES, label="Space", default="hall", **kw)
    if first.default == TOGGLE:
        return Param.toggle(field_name, default=False, **kw)
    lo, hi = min(s.lo for s in specs), max(s.hi for s in specs)
    if any(s.env for s in specs):
        return V.env(field_name, lo, hi, unit=first.unit, default=first.default, **kw)
    return Param.number(field_name, min=lo, max=hi, step=V.step(lo, hi, first.unit), unit=first.unit, default=first.default, **kw)


def params(kind="effect") -> list[Param]:
    """One Param per effect field; `kind` is the name of the value holding the effect's type."""
    by_name: dict[str, list[F]] = {}
    for fs in EFFECTS.values():
        for n, s in fs.items():
            by_name.setdefault(n, []).append(s)
    return [_param(n, specs, kind) for n, specs in by_name.items()]


def defaults(type_: str) -> dict:
    """What a new effect of this type stores (fields the engine has no default for are left out)."""
    out = {}
    for n, s in EFFECTS[type_].items():
        if s.default == BANDS:
            out[n] = []
        elif s.default == SPACE:
            out[n] = "hall"
        elif s.default == TOGGLE:
            out[n] = False
        elif s.default is not None:
            out[n] = s.default
    return out


def active(item: dict) -> dict:
    """The effect's values that apply to its type right now (what the engine is sent)."""
    fs = EFFECTS[item["effect"]]
    freeverb = str(item.get("space", "")).startswith("freeverb.")
    return {k: v for k, v in item.items() if k in fs and (k not in FREEVERB_ONLY or freeverb)}


def problems(item: dict) -> list[str]:
    """Per-type ranges a shared Param can't hold (gate threshold vs compressor threshold …)."""
    out = []
    for k, v in active(item).items():
        s = EFFECTS[item["effect"]][k]
        if s.lo is None or isinstance(v, bool):
            continue
        if isinstance(v, list):
            if not s.env:
                out.append(f"{item['id']}: {k} takes no envelope on a {item['effect']}")
                continue
            vals = [pt[1] for pt in v]
        else:
            vals = [v]
        if any(x < s.lo or x > s.hi for x in vals):
            out.append(f"{item['id']}: {k} on a {item['effect']} must be {s.lo} to {s.hi}{s.unit}")
    return out
