"""Painting on a mesh (SPEC §5): the 3D fields the shared painting kit (rostrum_paint) doesn't have. Part of the one
table (fields.FIELDS["mesh"] takes MESH; kind.py registers the kit with LAYER as its paint layers' own fields).

A mesh is a kit canvas: it holds `paints` (paint layers, bottom first) and `paintmasks`, in canvas pixels of a square
`paintSize` picture laid on its `uvs` (mesh.unfold). Each paint layer paints one surface channel (`channel`, shown as
"Paints"); paint_scene.py lays each channel's layers over the material's own value into a picture for both renderers.
"""
from __future__ import annotations

from rostrum_core import Param

from .fields import D, S

PAINTED = {"fact": "painted"}          # the mesh holds paint layers (kind.facts)

# channel -> (label, the material field the picture feeds, the material's own value under the paint, raw numbers?)
CHANNELS = {
    "colour": ("Colour", "baseColorTexture", "baseColor", False),
    "roughness": ("Roughness", "roughnessTexture", "roughness", True),
    "height": ("Height", "bumpTexture", None, True),
    "metal": ("Metal", "metallicTexture", "metallic", True),
    "glow": ("Glow", "emissionTexture", "emissionColor", False),
}

LAYER = [
    Param.choice("channel", list(CHANNELS), label="Paints", default="colour", importance=S,
                 labels={k: v[0] for k, v in CHANNELS.items()},
                 help="What the layer paints on the surface: Colour; Roughness (white = rough, black = mirror); Height "
                      "(white = raised, as bump); Metal (white = metal); Glow (its colours glow). Layers of one channel "
                      "stack; each sits over the material's own value where painted"),
]

MESH = [
    Param.number("paintSize", label="Paint size", group="Paint", min=256, max=8192, step=256, unit="px", integer=True,
                 default=2048, importance=D, valid_when=PAINTED,
                 help="The side of the square picture the paint is kept in, laid on the mesh's unfolded surface"),
    Param.list("uvs", "number", label="Unfolded surface", group="Mesh data", importance=D, default=[],
               help="mesh.unfold's result: one (u, v) per face corner of the mesh as drawn, flat [u0, v0, u1, v1, …]; "
                    "[] = the shape's own"),
]
