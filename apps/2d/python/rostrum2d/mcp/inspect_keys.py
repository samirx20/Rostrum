"""inspect_item, 2D's way: a layer's keys come as a summary by default (per field: how many, first and last time,
the values there), so a heavily keyed layer reads in a few lines; `keys: "all"` (or detail "full") lists every key.
The shared tool (rostrum_core) is wrapped here, as project_tool wraps inspect_project."""
from __future__ import annotations

import dataclasses
import re

from rostrum_core.keys import marked
from rostrum_core.mcp.tools import _schema_of

KEYS = {"keys": {"enum": ["summary", "all"], "default": "summary", "description":
                 "A part's keys: summary (per field) or all."}}


def summary(keys: list[dict]) -> dict:
    """{field: {"count", "first", "last", "from", "to"}} of an owner's keys, fields in the order first keyed."""
    out: dict = {}
    for k in sorted(keys, key=lambda k: marked.order(k["t"])):
        row = out.setdefault(k["prop"], {"count": 0, "first": k["t"], "from": _value(k)})
        row["count"] += 1
        row["last"], row["to"] = k["t"], _value(k)
    return out


def _value(k: dict):
    return next((k[f] for f in ("v", "c", "d") if f in k), None)


def _said(fields: dict) -> str:
    def t(x):
        return x if isinstance(x, str) else f"{x:g} s"
    return ", ".join(f'{p} {r["count"]} ({t(r["first"])}–{t(r["last"])})' if r["count"] > 1 else f'{p} 1 ({t(r["first"])})'
                     for p, r in fields.items())


def with_key_summary(runtime) -> None:
    old = runtime.tools.get("inspect_item")
    schema = {**old.schema, "properties": {**old.schema["properties"], **KEYS}}
    spec, _ = _schema_of(schema)

    def inspect_item(ctx, args):
        args = dict(args)
        want = args.pop("keys", "summary")
        reply = old.fn(ctx, args)
        kids = (reply.data.get("children") or {}).get("keys") if "id" in args else None
        if not kids or want == "all" or args.get("detail") == "full":
            return reply
        part = ctx.document(args.get("item")).item(args["id"])
        fields = summary(part.get("keys", []))
        reply.data["children"]["keys"] = {"count": kids["count"], "fields": fields,
                                          "more": 'inspect_item with keys "all" lists every key (id, time, value, ease)'}
        reply.summary = re.sub(r" keys: \d+ \([^)]*\)\.", f" keys: {kids['count']} on {len(fields)} field"
                               f"{'s' * (len(fields) != 1)}: {_said(fields)} (keys \"all\" lists each).", reply.summary)
        return reply
    runtime.tools._tools["inspect_item"] = dataclasses.replace(
        old, fn=inspect_item, schema=spec,
        description=old.description + ' A layer\'s keys come as a summary per field (count, first and last time and '
                                      'value); `keys: "all"` lists every key.')
