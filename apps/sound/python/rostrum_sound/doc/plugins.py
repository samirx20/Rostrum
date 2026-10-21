"""CLAP / VST3 plug-ins in the document: one record, `plugin`, on a "plugin" effect and on a "plugin" instrument.

    {"format": "clap" | "vst3", "path": "<file>", "id": "<plug-in id>", "name": "<shown name>",
     "params": {"<param id>": number | [[time, value], …]}, "state": "<base64>"}

`params` holds only what was changed (the plug-in's own default for the rest). A list value is the parameter's
automation lane, written "param:<id>" in plain words: the same envelope form every effect field takes. `state` is
what the plug-in's own window saved. `name` is for screens; the compiler leaves it out. The engine's `plugins`
request lists what is installed (engine.py). Plug-ins are never bundled: GPL ones may be loaded, not shipped.
"""
from __future__ import annotations

from rostrum_core import Param

from . import values as V

FORMATS = ["clap", "vst3"]
GROUP = "Plug-in"
_ANY = Param.number("value")


def _params(p, v, where):
    if not isinstance(v, dict):
        V._bad(p, v, where, "is not a set of plug-in settings", ['{"cutoff": 0.4, "mix": [[0, 0], [8, 1]]}'])
    return {str(k): V._env(_ANY, x, f"{where} › {k}") for k, x in v.items()}


PARAMS = V.Value("params", "text", rule=_params, group=GROUP, importance="secondary",
                 help="Settings that differ from the plug-in's defaults: {param id: number or [[time, value], …]} "
                      "(a list is that parameter's lane, \"param:<id>\").", schema={
                          "type": "object", "additionalProperties": {"anyOf": [{"type": "number"}, {"type": "array"}]}})
_FIELDS = [Param.choice("format", FORMATS, required=True), Param.text("path", required=True),
           Param.text("id", required=True), Param.text("name"), PARAMS, Param.text("state")]
_rule, _schema = V.fields_of(_FIELDS, "plug-in")


def record(when) -> V.Value:
    """The `plugin` field of an effect or a track, present only while `when` holds (rule of individuality)."""
    return V.Value("plugin", "text", rule=_rule, schema=_schema, group=GROUP, valid_when=when, importance="deep",
                   help="The plug-in: {format, path, id, name?, params?, state?}; inspect_plugins lists what is installed.")


def problems(item: dict, what: str) -> list[str]:
    """A plug-in effect or instrument must name its plug-in."""
    return [] if item.get("plugin") else [f"{what}: needs its plugin ({{format, path, id}}); inspect_plugins lists them"]


def engine_form(spec: dict, env=lambda v, where: v, where="plugin") -> dict:
    """The contract's plug-in object: the record without its display `name`, times in the params resolved."""
    out = {k: v for k, v in spec.items() if k != "name" and (v or k in ("format", "path", "id"))}
    if "params" in out:
        out["params"] = {k: env(v, f"{where}.params.{k}") for k, v in out["params"].items()}
    return out
