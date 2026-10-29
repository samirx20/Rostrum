"""Sculpt layers (PR4): a group of a clay's strokes with an Amount, as a smile or a frown on a face. A layer is a
`claylayer` item in the clay's `sculptLayers` list; a step that belongs to one names it in its `layer` (none: the
Base). The clay's `sculptLayer` says where the next stroke or piece goes (ops_clay_layers.py).

How the shape is made (clay_scene.chain, the one rule): first every Base step in order, then each layer's steps,
layer by layer in list order. A layer's stroke works at its strength × Amount; a ball piece on a layer has its radius
× Amount (a horn grows); a drawn, spun or from-an-item piece is in while Amount is above 0. A layer at Amount 0 or
switched off (`on`) leaves the clay as if it weren't there. So a layer can be dialled from nothing to full without
touching the Base, and the steps after it are never replayed when its Amount changes: only that layer and the ones
below it in the list are.
"""
from __future__ import annotations

import dataclasses

from .field_kit import D, N, P, S, T, X

LIST, NEXT, STEP_FIELD = "sculptLayers", "sculptLayer", "layer"

LAYER = [
    X("name", "Name", "Layer", "", P, help='What the layer is ("smile", "frown", "blink"); the Layers list shows it'),
    dataclasses.replace(N("amount", "Amount", "Layer", 0, 1, 0.01, "", P, default=1.0,
                          help="How much of the layer's strokes show: 0 = none, 1 = as sculpted"), display="percent"),
    T("on", "On", "Layer", True, S, help="Off: the clay as if the layer weren't there; its strokes are kept"),
]

STEP = X(STEP_FIELD, "Layer", "Step", "", D, refers="claylayer",
         help="The sculpt layer the step belongs to (\"\" = the Base): it is applied after every Base step, at the "
              "layer's Amount")
NEXT_FIELD = X(NEXT, "Sculpt on", "Brush", "", D, refers="claylayer",
               help='The sculpt layer the next stroke or piece goes on ("" = the Base); claylayer.add sets it')


def layers(clay: dict) -> list[dict]:
    return clay.get(LIST) or []


def amounts(clay: dict, values=None) -> dict[str, float]:
    """{layer id: the Amount it works at now} (0 when off). `values(layer id)` gives its fields at the frame the scene
    is built for (compile.py's evaluator); without it, the stored values."""
    out = {}
    for lay in layers(clay):
        v = values(lay["id"]) if values else lay
        out[lay["id"]] = float(v.get("amount", 1.0)) if v.get("on", True) else 0.0
    return out


def ordered(steps: list[dict], clay: dict, amount: dict[str, float] | None = None) -> list[tuple[dict, float]]:
    """(step, its layer's Amount) in the order the clay is made: the Base's steps, then each layer's in list order;
    steps at Amount 0 are left out. A step naming a layer that is gone counts as the Base's."""
    amount = amounts(clay) if amount is None else amount
    base = [(s, 1.0) for s in steps if s.get(STEP_FIELD, "") not in amount]
    out = list(base)
    for lay in layers(clay):
        a = amount.get(lay["id"], 0.0)
        if a > 0:
            out += [(s, a) for s in steps if s.get(STEP_FIELD, "") == lay["id"]]
    return out


def scaled(step: dict, a: float) -> dict:
    """A step as its layer's Amount makes it (1: itself)."""
    if a >= 1.0:
        return step
    if step.get("step") == "stroke":
        return {**step, "strength": float(step.get("strength", 0.5)) * a}
    if step.get("shape", "sphere") in ("sphere", "capsule"):
        return {**step, "radius": float(step.get("radius", 0.1)) * a}
    return step


def check(clay: dict, problems: list):
    """Every step's layer and the clay's Sculpt on name a layer of this clay."""
    own = {lay["id"] for lay in layers(clay)}
    for s in clay.get("steps", []):
        if s.get(STEP_FIELD) and s[STEP_FIELD] not in own:
            problems.append(f'{clay["id"]} step {s["id"]}: no sculpt layer "{s[STEP_FIELD]}" on this clay (`layer`)')
    if clay.get(NEXT) and clay[NEXT] not in own:
        problems.append(f'{clay["id"]}: no sculpt layer "{clay[NEXT]}" on this clay (`{NEXT}`)')
