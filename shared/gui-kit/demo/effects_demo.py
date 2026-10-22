"""A demo document whose rectangles take effects (child items with their own settings), for the Effects row's look
harness and test. Not an app: 2D has the real ones (effect.add / effect.remove, one field operation per effect)."""
from __future__ import annotations

from rostrum_core import toy
from rostrum_core.document import Document
from rostrum_core.kind import DocKind
from rostrum_core.params import Param
from rostrum_core.registry import Registry

from rostrum_gui.effects import EffectsSpec, EffectType


def N(name, label, group, lo, hi, step, unit="", imp="primary", default=None):
    return Param.number(name, label=label, group=group, min=lo, max=hi, step=step, unit=unit, importance=imp, default=default)


EFFECTS = {
    "blur": ("Blur", [N("radius", "Blur radius", "Blur", 0, 200, 0.5, "px", default=8),
                      Param.toggle("edges", label="Keep the edges sharp", group="Blur", importance="secondary", default=False)],
             dict(radius=8, edges=False)),
    "glow": ("Glow", [N("radius", "Glow radius", "Glow", 0, 200, 0.5, "px", default=24),
                      N("amount", "Amount", "Glow", 0, 1, 0.01, default=0.6),
                      Param.color("color", label="Colour", group="Glow", default="#ffe2c4")], dict(radius=24, amount=0.6, color="#ffe2c4")),
    "shadow": ("Shadow", [N("dx", "Across", "Shadow", -500, 500, 1, "px", default=0),
                          N("dy", "Down", "Shadow", -500, 500, 1, "px", default=12),
                          N("soft", "Softness", "Shadow", 0, 200, 1, "px", "secondary", 24)], dict(dx=0, dy=12, soft=24)),
}
REGISTRY = Registry()
for _kind, (_label, _params, _) in EFFECTS.items():
    REGISTRY.operation(f"{_kind}.set", f"Change a {_label.lower()}.", target=_kind, params=_params, fields=True,
                       label=f"Edit {_label.lower()}")(toy._set_fields)
RECT = [N("x", "X", "Position", -4000, 4000, 1, "px", default=0), N("y", "Y", "Position", -4000, 4000, 1, "px", default=0),
        N("w", "Width", "Size", 0, 8000, 1, "px", default=200), N("h", "Height", "Size", 0, 8000, 1, "px", default=120),
        Param.color("fill", label="Fill", group="Look", default="#4c8dff"),
        N("radius", "Corner radius", "Look", 0, 1000, 1, "px", "secondary", 8)]
REGISTRY.operation("rect.set", "Change a rectangle's settings.", target="rect", params=RECT, fields=True,
                   label="Edit rectangle")(toy._set_fields)


@REGISTRY.operation("effect.add", "Add an effect to rectangles.", target="rect", label="Add effect",
                    params=[Param.choice("type", list(EFFECTS), label="Effect", required=True)])
def effect_add(ctx, targets, args):
    for t in targets:
        t_ = args["type"]
        ctx.insert(t, "effects", {"id": ctx.new_id(t_), "type": t_, **EFFECTS[t_][2]})


@REGISTRY.operation("effect.remove", "Remove effects.", target=tuple(EFFECTS), label="Remove effect")
def effect_remove(ctx, targets, args):
    for t in targets:
        ctx.remove(t)


KIND = DocKind("fxdemo", ".fxdemo", REGISTRY, lists={"doc": ["layers"], "rect": ["effects"]},
               new=lambda: {"id": "root", "type": "doc", "layers": []})
SPEC = EffectsSpec(types=[EffectType(k, v[0]) for k, v in EFFECTS.items()], kinds=("rect",))


def sample() -> Document:
    """One rectangle ("card") with a blur and a glow already on it, and a second with none."""
    data = KIND.blank()
    card = {"id": "card", "type": "rect", "name": "Card", **toy.DEFAULTS["rect"], "radius": 24,
            "effects": [{"id": "blur_1", "type": "blur", **EFFECTS["blur"][2]},
                        {"id": "glow_1", "type": "glow", **EFFECTS["glow"][2]}]}
    data["layers"] = [card, {"id": "plain", "type": "rect", "name": "Plain", **toy.DEFAULTS["rect"]}]
    return Document(KIND, data)
