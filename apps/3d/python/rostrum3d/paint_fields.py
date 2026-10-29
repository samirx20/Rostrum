"""Painting on a mesh or a clay (SPEC §5): the 3D fields the shared painting kit (rostrum_paint) doesn't have. Part of
the one table (mesh_fields.MESH takes MESH, clay_fields.CLAY takes SIZE; kind.py registers the kit with LAYER as its
paint layers' own fields and STROKE as its strokes').

A mesh or a clay is a kit canvas: it holds `paints` (paint layers, bottom first) and `paintmasks`, in canvas pixels of
a square `paintSize` picture laid on its unfolded surface (a mesh's `uvs`, mesh.unfold; a clay's, made by the core for
each shape: clay_paint.py). Each paint layer paints one surface channel (`channel`, shown as "Paints"); paint_scene.py
lays each channel's layers over the material's own value into a picture for both renderers. A clay's strokes are kept
on its surface (`anchors`, `reach`), so they stay on the same spots when the clay is reshaped and unfolded anew.

Painting **from the view** (paint_view.py): a stroke may be kept as drawn through a camera (`viewPoints` in the
pixels of a `viewSize` picture from `viewEye` looking at `viewTarget` with `viewFov`, at `viewFrame`; its `size` in
screen px), laid on the canvas each time the canvas is made. A layer may hold a picture projected from a camera
(`projectSource`, a file or "2d:<2D item id>", with the same camera fields `project…`). The core has no field kind for
a nested object, so each is flat fields; paint_view.view_of / projected_of give them as one dict.
"""
from __future__ import annotations

from rostrum_core import Param

from .field_kit import D, S

XYZ = dict(min_items=3, max_items=3, unit="m", importance=D, default=None, nullable=True)
WH = dict(min_items=2, max_items=2, unit="px", importance=D, default=None, nullable=True, integer=True)


def _camera(prefix: str, group: str, what: str) -> list:
    """The camera fields a view stroke or a projected picture keeps: where it looked from, at, how wide, how big."""
    return [
        Param.list(f"{prefix}Eye", "number", label="Camera at", group=group, **XYZ,
                   help=f"Where the camera stood when {what} (world x y z, metres)"),
        Param.list(f"{prefix}Target", "number", label="Looking at", group=group, **XYZ,
                   help=f"The point in the middle of that picture (world x y z, metres)"),
        Param.number(f"{prefix}Fov", label="Field of view", group=group, min=0.1, max=179, unit="°", importance=D,
                     default=None, nullable=True, help="The picture's height as an angle (degrees, vertical)"),
        Param.list(f"{prefix}Size", "number", label="Picture size", group=group, **WH,
                   help="[width, height] of that picture in px"),
        Param.number(f"{prefix}Frame", label="Frame", group=group, min=0, max=10_000_000, integer=True, importance=D,
                     default=None, nullable=True, help="The scene frame the camera saw (the surfaces as they were then)"),
    ]

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
    Param.text("projectSource", label="Projected picture", group="Projected", importance=D, default=None, nullable=True,
               help="A picture projected onto the item from a camera (paint.project): a picture file, or \"2d:<2D item "
                    "id>\" for that 2D item's newest pictures render (repainting it in 2D updates it). Laid on the "
                    "texels the camera sees (paint_view.py); the layer's own strokes paint over it. \"\" = none"),
    *_camera("project", "Projected", "the picture was projected"),
    Param.choice("channel", list(CHANNELS), label="Paints", default="colour", importance=S,
                 labels={k: v[0] for k, v in CHANNELS.items()},
                 help="What the layer paints on the surface: Colour; Roughness (white = rough, black = mirror); Relief "
                      "(`height`: unpainted is middle grey, flat; white = raised, black = sunk, as bump: fine detail such as wrinkles, pores, "
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
    Param.points("viewPoints", label="From the view", min=2, max=3, importance=D, group="Path", default=None,
                 nullable=True,
                 help="A stroke from the view: its path as drawn, [[x, y, pressure], …] in px of the `viewSize` picture "
                      "through the camera `viewEye` → `viewTarget` (`viewFov`, `viewFrame`); its `size` is in screen "
                      "px. Laid on the surface the camera sees there each time the paint is made (moving the item "
                      "re-lands it); `points` may be left out. Drawn across several items it is kept on each"),
    *_camera("view", "Path", "the stroke was drawn"),
    Param.number("stampTurn", label="Stamp turn", min=-360, max=360, unit="°", group="Path", importance=D,
                 default=None, nullable=True,
                 help="A stamp's turn as asked (paint.stamp): its `angle` is worked out each time it is laid so that 0 "
                      "is upright (from the view: the screen's up; on a clay: its +Y on the surface), then turned "
                      "clockwise by this (stamp_turn.py). Left out = the angle is used as it is"),
    Param.text("viewShot", label="Drawn through", group="Path", importance=D, default=None, nullable=True,
               help="The shot whose camera the stroke was drawn through, when it was (for reports)"),
]

MESH = [
    SIZE,
    Param.list("uvs", "number", label="Unfolded surface", group="Mesh data", importance=D, default=[],
               help="mesh.unfold's result: one (u, v) per face corner of the mesh as drawn, flat [u0, v0, u1, v1, …]; "
                    "[] = the shape's own"),
]


def check_strokes(canvas: dict, problems: list):
    """A mesh's strokes have `points` or a view (`viewPoints` with its camera); a clay's also `anchors` with `reach`."""
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
            elif s.get("viewPoints") and any(s.get(f"view{k}") is None for k in ("Eye", "Target", "Fov", "Size")):
                problems.append(f"{where}: a stroke from the view needs its camera: viewEye, viewTarget, viewFov, "
                                "viewSize (and viewFrame)")
            elif not s.get("points") and not s.get("anchors") and not s.get("viewPoints"):
                problems.append(f"{where}: has no path: give `points` (canvas px) or `viewPoints` (from the view)"
                                + (" or `anchors` (on the clay's surface) and `reach`" if clay else ""))
    for layer in canvas.get("paints", []):
        if layer.get("projectSource") and any(layer.get(f"project{k}") is None for k in ("Eye", "Target", "Fov", "Size")):
            problems.append(f'{canvas["id"]} layer {layer["id"]}: a projected picture needs its camera: projectEye, '
                            "projectTarget, projectFov, projectSize (paint.project sets them)")
