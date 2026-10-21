"""A text that follows a path layer: the text keeps only the path layer's id (`pathLayer`); the engine resolves it on
every frame (engine scene/follow.rs: the path's shape, box, transform and trim window at that time). This module is
the Python side of the same rule: `text.follow` (sets the reference, checked), `problem` (a reference that no longer
resolves, said in words for inspect / look) and `taken` (the path's values a following text shows at a time, for
the approximate boxes in mcp/geometry.py). A text and its path sit side by side, in the same composition or group.
"""
from __future__ import annotations

from rostrum_core import Param
from rostrum_core.errors import codes

from . import fields as F
from .evaluate import resolve
from .kind import LISTS, REGISTRY as R


def _target(text: dict, siblings: list[dict]) -> tuple[dict | None, str]:
    """(the path layer `text` follows, "") or (None, what is wrong)."""
    want = text.get("pathLayer", "")
    found = next((s for s in siblings if s["id"] == want), None)
    if found is None:
        return None, (f'{text["id"]} follows the path layer "{want}", which is gone (deleted, or not in the same group): '
                      f'pick a path layer beside it (text.follow) or clear pathLayer. Until then this composition can\'t be drawn.')
    if found["type"] != "path":
        return None, f'{text["id"]} follows "{want}", which is a {found["type"]} layer, not a path'
    return found, ""


def following(layer: dict) -> bool:
    return layer.get("type") == "text" and bool(layer.get("pathLayer"))


def problem(layer: dict, siblings: list[dict]) -> str:
    """Why a following text's path doesn't resolve ("" when it does, or it follows none)."""
    return _target(layer, siblings)[1] if following(layer) else ""


def problems(comp: dict) -> list[str]:
    """Every broken path reference in a composition, groups included."""
    out = []

    def walk(layers):
        for layer in layers:
            if msg := problem(layer, layers):
                out.append(msg)
            walk(layer.get("layers", []))
    walk(comp.get("layers", []))
    return out


def taken(layer: dict, siblings: list[dict], t: float) -> dict | None:
    """The path layer's values a following text takes at time t (its transform fields, w, h); None if none."""
    path, _ = _target(layer, siblings) if following(layer) else (None, "")
    if path is None:
        return None
    p = resolve(path, t)
    return {**{f: p[f] for f in F.TAKEN}, "w": p["w"], "h": p["h"]}


def _parent_layers(ctx, id_: str) -> list[dict]:
    from rostrum_core.tree import index
    for entry in index(ctx.doc, ctx.kind.lists).values():
        layers = entry.item.get("layers") if "layers" in LISTS.get(entry.item.get("type"), []) else None
        if layers and any(l["id"] == id_ for l in layers):
            return layers
    return []


@R.operation("text.follow", "Make a text follow a path layer beside it (same composition or group): its letters sit on that "
             "path as the path is reshaped, moved, turned or drawn on (trim), on every frame. The text takes the path's place "
             "and turn; its own path data is cleared. path empty = stop following (the text keeps the path's place).",
             target="text", label="Follow path",
             params=[Param.text("path", label="Path layer", help="The id of a path layer in the same group; empty = stop following")])
def text_follow(ctx, targets, args):
    want = args.get("path", "")
    for t in targets:
        text, siblings = ctx.item(t), _parent_layers(ctx, t)
        if not want:
            if following(text) and (now := taken(text, siblings, 0.0)):
                for f in F.TAKEN:
                    ctx.set(t, f, now[f])
            ctx.set(t, "pathLayer", "")
            continue
        _, wrong = _target({**text, "pathLayer": want}, siblings)
        if wrong:
            ctx.fail(codes.BAD_ARGUMENT, f'path "{want}"', wrong.split(": pick")[0],
                     [s["id"] for s in siblings if s["type"] == "path"], hint="Give a path layer in the same group.")
        ctx.set(t, "path", "")
        ctx.set(t, "pathLayer", want)
