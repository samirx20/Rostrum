"""`paint.export` (SPEC PR6): a painted mesh's or clay's pictures written to a folder as UDIM sets with a manifest
(paint_export.py), so Mari, Substance or a game engine reads them. Changes nothing in the document.

The pictures come from the scene as the renderers get it: the document's first shot compiled (compile.describe) and,
when some paint waits for the engine (a clay's unfold, paint from the view), finished with this app's engine
(`use_engine`, set beside ops_mesh's).
"""
from __future__ import annotations

from pathlib import Path

from rostrum_core import Param
from rostrum_core.errors import codes

from . import compile as C, paint_export, paint_scene
from .kind import REGISTRY as R

_ENGINE = None
_FOLDER = None


def use_engine(engine, folder=None):
    """The engine (and project folder) that finishes paint waiting for it; None: only paint needing no engine."""
    global _ENGINE, _FOLDER
    _ENGINE, _FOLDER = engine, folder


def painted_scene(doc: dict, folder=None) -> dict:
    """The document's first shot as the renderers get it, every painted item's pictures made."""
    shots = doc.get("shots") or []
    if not shots:
        raise ValueError("the document has no shot yet, so its scene can't be built (shot.add first)")
    scene = C.describe(doc, shots[0]["id"], folder)
    later = scene.get(paint_scene.LATER)
    if not later:
        return scene
    if _ENGINE is None:
        raise ValueError("some paint needs the 3D engine to be laid (a clay's, or paint from the view), and there is "
                         "none here: run it in the app or through the 3D MCP server")
    _ENGINE.ensure_scene(scene)                          # loads it, so the clays' unfolds and texel pictures exist
    return paint_scene.finish(paint_scene.engine_scene(scene), later, _ENGINE.texels_reply)


@R.operation("paint.export", "Export painted pictures: each channel a painted mesh or clay paints (colour, roughness, "
             "metal, relief, glow), as rendered (its paint over its material), written to `folder` as a UDIM set "
             "`<item>_<channel>.1001.png` (one tile: paint is one picture on the item's unfold), plus "
             "`<item>_paint.json` listing channel -> file, so a studio tool (Mari, Substance, a game engine) reads them. "
             "An editable mesh's painted face materials go out as `<item>__<material>_<channel>.1001.png`. Fails on "
             "an item with no paint. Changes nothing in the document.",
             target=("mesh", "clay"), label="Export painted pictures", importance="secondary",
             params=[Param.text("folder", label="Folder", required=True,
                                help="Where the pictures go: an absolute folder, or one inside the project folder "
                                     "(made when missing)")])
def paint_export_op(ctx, targets, args):
    folder = _FOLDER                                     # an operation sees only the document: the engine's project
    dest = Path(args["folder"])
    if not dest.is_absolute():
        if not folder:
            ctx.fail(codes.BAD_ARGUMENT, '"folder"', f'"{args["folder"]}" is not absolute and there is no project folder',
                     hint="Give an absolute folder.")
        dest = Path(folder) / dest
    unpainted = [t for t in targets if not paint_export.painted_channels(ctx.item(t))]
    if unpainted:
        ctx.fail(codes.BAD_ARGUMENT, "target", f'{", ".join(unpainted)} has no paint, so there is nothing to export',
                 hint="Paint it first (a paint layer on the item), or pick a painted item.")
    try:
        scene = painted_scene(ctx.doc, folder)
        out = {t: paint_export.export(scene, ctx.item(t), dest) for t in targets}
    except (ValueError, RuntimeError, OSError) as e:
        ctx.fail(codes.BAD_ARGUMENT, "target", f"its painted pictures could not be exported: {e}")
    return {"folder": str(dest), "items": out}
