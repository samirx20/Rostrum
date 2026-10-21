"""Expressions in the inspector: a field driven by an expression or binding shows its text where the widget would
be, with a clear button; every other field shows nothing extra (rule of individuality). No Qt."""
from __future__ import annotations

from rostrum2d import fields as F
from rostrum_core.keys import keys_of
from rostrum2d.exprbake import source_of


def drives(item: dict, prop: str) -> bool:
    return bool(item.get("exprs")) and bool(source_of(item, prop))


def state(item: dict, prop: str):
    """The row's text (`logo.x * 2 + 10`) and a note on what it does to the field's own keys; "" when none."""
    if not drives(item, prop):
        return ""
    return {"text": source_of(item, prop), "note": "overrides its keys" if keys_of(item, prop) else ""}


def clear_calls(item: dict, prop: str) -> tuple[list[dict], str]:
    """(calls, history label) for the clear button."""
    return ([{"op": "expr.clear", "target": [item["id"]], "args": {"prop": prop}}],
            f"Clear expression on {F.param(item['type'], prop).label}")
