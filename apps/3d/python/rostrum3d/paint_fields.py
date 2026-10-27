"""Painting on a mesh or a clay (SPEC §5): the 3D fields the shared painting kit (rostrum_paint) doesn't have. Part of
the one table (mesh_fields.MESH takes MESH, clay_fields.CLAY takes SIZE; kind.py registers the kit with LAYER as its
paint layers' own fields and STROKE as its strokes').

A mesh or a clay is a kit canvas: it holds `paints` (paint layers, bottom first) and `paintmasks`, in canvas pixels of
a square `paintSize` picture laid on its unfolded surface (a mesh's `uvs`, mesh.unfold; a clay's, made by the core for
each shape: clay_paint.py). Each paint layer paints one surface channel (`channel`, shown as "Paints"); paint_scene.py
lays each channel's layers over the material's own value into a picture for both renderers. A clay's strokes are kept
on its surface (`anchors`, `reach`), so they stay on the same spots when the clay is reshaped and unfolded anew.
"""
from __future__ import annotations

from rostrum_core import Param

from .field_kit import D, S

PAINTED = {"fact": "painted"}          # the mesh or clay holds paint layers (kind.facts)

# channel -> (label, the material field the picture feeds, the material's own value under the paint, raw numbers?)
CHANNELS = {
    "colour": ("Colour", "baseColorTexture", "baseColor", False),
    "roughness": ("Roughness", "roughnessTexture", "roughness", True),
    "height": ("Relief", "bumpTexture", None, True),          # shown as Relief; the key stays (old projects open)
    "metal": ("Metal", "metallicTexture", "metallic", True),
    "glow": ("Glow", "emissionTexture", "emissionColor", False),
}

LAYER = [
    Param.choice("channel", list(CHANNELS), label="Paints", default="colour", importance=S,
                 labels={k: v[0] for k, v in CHANNELS.items()},
                 help="What the layer paints on the surface: Colour; Roughness (white = rough, black = mirror); Relief "
                      "(`height`: white = raised, black = sunk, as bump: fine detail such as wrinkles, pores, "
                      "scratches); Metal (white = metal); Glow (its colours glow). Layers of one channel stack; each "
                      "sits over the material's own value where painted"),
]

SIZE = Param.number("paintSize", label="Paint size", group="Paint", min=256, max=8192, step=256, unit="px", integer=True,
                    default=2048, importance=D, valid_when=PAINTED,
                    help="The side of the square picture the paint is kept in, laid on the unfolded surface")

STROKE = [
    Param.points("anchors", label="On the surface", min=7, max=7, importance=D, group="Path", default=None,
                 nullable=True,
                 help="A clay's stroke: its path on the surface, [[x, y, z, nx, ny, nz, pressure], …] in the clay's own "
                      "space (metres; look_at's `local` and `localNormal`). Its `points` are laid from them on the "
                      "clay's surface as it is now, so the paint stays on the same spots when the clay is reshaped; "
                      "with anchors, `points` may be left out"),
    Param.number("reach", label="Reach", min=0.00001, max=100, step=0.001, unit="m", importance=D, group="Path",
                 default=None, nullable=True,
                 help="A clay stroke's brush radius on the surface, in metres (with `anchors`): its `size` in pixels "
                      "is worked out from it where the stroke lands"),
]

MESH = [
    SIZE,
    Param.list("uvs", "number", label="Unfolded surface", group="Mesh data", importance=D, default=[],
               help="mesh.unfold's result: one (u, v) per face corner of the mesh as drawn, flat [u0, v0, u1, v1, …]; "
                    "[] = the shape's own"),
]


def check_strokes(canvas: dict, problems: list):
    """A mesh's strokes have `points`; a clay's have `points` or `anchors` with `reach`."""
    clay = canvas.get("type") == "clay"
    for layer in canvas.get("paints", []):
        for s in layer.get("strokes", []):
            if s.get("type") != "stroke":
                continue
            where = f'{canvas["id"]} stroke {s["id"]}'
            if s.get("anchors") and not clay:
                problems.append(f"{where}: `anchors` are for a clay's strokes; a mesh's stroke is laid by `points`")
            elif s.get("anchors") and not s.get("reach"):
                problems.append(f"{where}: a stroke with `anchors` needs `reach` (its brush radius in metres)")
            elif not s.get("points") and not s.get("anchors"):
                problems.append(f"{where}: has no path: give `points` (canvas px)"
                                + (" or `anchors` (on the clay's surface) and `reach`" if clay else ""))
