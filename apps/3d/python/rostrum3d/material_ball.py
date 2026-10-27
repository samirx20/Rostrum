"""A material seen on a ball, the parts that need no screen: which fields a ball shows (the picker's balls and look_material) and
whether the material needs Final (Cycles) to be seen as it will render."""
from __future__ import annotations

from . import fields as F
from .material_fields import FINAL_ONLY, QUICK_APPROX

BALL_SHAPE = {"shape": "sphere", "radius": 0.5, "segments": 48}     # the picker's ball (a unit-ish sphere)


def ball_values(values: dict) -> dict:
    """The material fields that apply (a whole material item may be given): ids, names and switched-off settings go,
    and a 2D render (a project's own file) is left out of the ball."""
    names = {p.name for p in F.FIELDS["material"]} - {"emissionRender"}
    kept = {k: v for k, v in values.items() if k in names}
    off = set(F.not_valid("material", {**F.defaults("material"), **kept}, kept))
    return {k: v for k, v in kept.items() if k not in off}


def final_reasons(values: dict) -> list[str]:
    """Why a quick look (Storm) would misjudge this material, in words ([] when Storm shows it fairly)."""
    v, base = {**F.defaults("material"), **ball_values(values)}, F.defaults("material")
    out = []
    if v["transmission"] > 0:
        out.append(f'glass: transmission {v["transmission"]:g} lets light through and bends it, which Storm only fakes')
    if v["metallic"] >= 0.3:
        out.append(f'metal: metallic {v["metallic"]:g} is mostly reflection, and Storm reflects only a blurred sky')
    if v["coat"] > 0:
        out.append(f'clear coat {v["coat"]:g}: a second reflection layer Storm does not draw')
    out += [f"{k} {v[k]!r} is applied by Cycles only" for k in sorted(FINAL_ONLY | QUICK_APPROX) if v.get(k) != base.get(k)]
    return out
