"""Starting points for a new material (SPEC §6.1): the physical settings of a substance, never a look. Each start is
only values of the one material type (material_fields.MATERIAL); a new material copies them once (`material.from`)
and is then an ordinary material, edited field by field. Colour is neutral grey unless it is part of the substance
(wood is brown; a screen's base is dark because it is glass over a black panel).

The picker shows them in this order, the clay work's four first (SPEC §5): a new clay starts as Clay. Skin and wax
carry light under the surface; its distances are measured ones (Jensen et al. 2001, the diffuse mean free path per
colour: skin about 3.7 / 1.4 / 0.7 mm for red / green / blue, marble 8.5 / 5.6 / 4.0 mm), written as the farthest
distance (`subsurfaceRadius`) and the colour whose channels are the others' share of it (`subsurfaceColor`, sRGB).
"Painted (ramp)" and "Ink & flat" (SPEC §6.1) are the stylized blocks' settings switched on over a matte surface:
Light to colour with its bands in neutral greys (white lit, so the base colour itself shows where it is lit), and for
Ink & flat lines on too. Their bands are physical settings (how much light makes a band), never a colour scheme: a
person or an agent picks the colours afterwards.
Fabric's sheen is the colour of its fibres (a dyed thread scatters its dye's colour): its sheen colour is its base colour,
and a fabric made with another base colour gets that one as its sheen colour too (start_values). A white sheen over a
dyed cloth turned every flat, top-lit stretch of it pale pink-white like paper (round 5 of the 3D gaps, Drape r2).
"""
from __future__ import annotations

STARTS: dict[str, dict] = {
    "clay": {"label": "Clay", "values": {"baseColor": "#a6a6a6", "roughness": 0.75}},    # modelling clay is duller than matte plastic (0.7)
    "skin": {"label": "Skin", "values": {"baseColor": "#c49a84", "roughness": 0.45, "ior": 1.4, "subsurface": 1,
                                         "subsurfaceColor": "#ffa477", "subsurfaceRadius": 3.7}},
    "wax": {"label": "Wax / soap", "values": {"baseColor": "#e8e2d4", "roughness": 0.3, "ior": 1.45, "subsurface": 1,
                                              "subsurfaceColor": "#ffe4cc", "subsurfaceRadius": 8}},
    "stone": {"label": "Stone", "values": {"baseColor": "#8a8780", "roughness": 0.8}},
    "matte plastic": {"label": "Matte plastic", "values": {"baseColor": "#b3b3b3", "roughness": 0.7}},
    "glossy plastic": {"label": "Glossy plastic", "values": {"baseColor": "#b3b3b3", "roughness": 0.15}},
    "rubber": {"label": "Rubber", "values": {"baseColor": "#3a3a3a", "roughness": 0.85, "sheen": 0.15,
                                             "sheenRoughness": 0.8}},
    "polished metal": {"label": "Polished metal", "values": {"baseColor": "#d6d6d6", "metallic": 1, "roughness": 0.08}},
    "brushed metal": {"label": "Brushed metal", "values": {"baseColor": "#c8c8c8", "metallic": 1, "roughness": 0.35,
                                                           "anisotropy": 0.7, "brushDirection": "uv"}},
    "glass": {"label": "Glass", "values": {"baseColor": "#ffffff", "transmission": 1, "ior": 1.5, "roughness": 0}},
    "frosted glass": {"label": "Frosted glass", "values": {"baseColor": "#ffffff", "transmission": 1, "ior": 1.5,
                                                           "roughness": 0.25}},
    "ceramic": {"label": "Ceramic", "values": {"baseColor": "#e0e0e0", "roughness": 0.3, "coat": 1,
                                               "coatRoughness": 0.05, "ior": 1.5}},
    "fabric": {"label": "Fabric", "values": {"baseColor": "#8c8c8c", "roughness": 0.9, "sheen": 0.6,
                                             "sheenRoughness": 0.6, "sheenTint": "#8c8c8c"}},   # dyed fibres shine in their dye
    "wood": {"label": "Wood", "values": {"baseColor": "#8a5a36", "roughness": 0.55}},
    "car paint": {"label": "Car paint", "values": {"baseColor": "#8c8c8c", "roughness": 0.4, "coat": 1,
                                                   "coatRoughness": 0.03}},
    "painted": {"label": "Painted (ramp)", "values": {"baseColor": "#b3b3b3", "roughness": 0.7, "lightToColor": True,
                                                      "lightEdges": "smooth", "lightSoftness": 0.12,
                                                      "litColor": "#ffffff", "midColor": "#b3b3b3",
                                                      "shadowColor": "#4d4d4d", "shadowBelow": 0.15, "litFrom": 0.5}},
    "ink and flat": {"label": "Ink & flat", "values": {"baseColor": "#b3b3b3", "roughness": 0.7, "lightToColor": True,
                                                       "lightEdges": "steps", "litColor": "#ffffff",
                                                       "midColor": "#808080", "shadowColor": "#808080",
                                                       "shadowBelow": 0.3, "litFrom": 0.3, "lines": True}},
    "screen": {"label": "Screen", "values": {"baseColor": "#0a0a0a", "roughness": 0.1, "emissionStrength": 2,
                                             "emissionColor": "#ffffff"}},
}


def start_key(name: str) -> str | None:
    """A start's key from its key or label, any case ("Brushed metal", "brushed metal", "Wax / soap", "wax"); None
    when there is none."""
    n = str(name).strip().lower()
    return n if n in STARTS else next((k for k, s in STARTS.items() if s["label"].lower() == n), None)


def start_values(key: str, given: dict) -> dict:
    """A start's values with the given fields on top. A start value the given ones switch off (the base colour once a
    base colour image is given) is dropped, so a start never refuses a field; a given field that doesn't apply still
    fails loudly where it is written."""
    from . import fields as F
    start = STARTS[key]["values"]
    merged = {**start, **given}
    for k in ("sheenTint",):                                    # a start's colour that is its base colour follows it
        if k not in given and start.get(k) == start["baseColor"] and "baseColor" in given:
            merged[k] = given["baseColor"]
    item = {**F.defaults("material"), **merged}
    off = set(F.not_valid("material", item, [k for k in start if k not in given]))
    return {k: v for k, v in merged.items() if k not in off}
