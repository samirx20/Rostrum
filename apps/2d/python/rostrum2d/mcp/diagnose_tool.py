"""inspect_diagnose: everything wrong in a composition, in one list (rostrum2d/diagnose.py + diagnose_engine.py)."""
from __future__ import annotations

from rostrum_core import markers
from rostrum_core.mcp import Reply, Tools

from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


@tools.tool("inspect_diagnose", {"properties": {**ITEM_COMP, "engine": {
    "type": "boolean", "description": "Also ask the engine (fonts it can't find, anything it refuses when the scene loads). Default true."}}})
def inspect_diagnose(ctx, args):
    """Everything wrong in a composition, each with the item, what is wrong in words and how to fix it. Kinds:
    refused (the engine won't draw the scene), missing-font, missing-file (image, video, LUT; names the layer and the file), outside-project (a file kept outside the project folder: it will not travel with it), broken-link (a text's
    path layer, a track matte), missing-marker (an expression's marker("…")), expression, invisible (a layer never
    seen: opacity 0, zero size, outside its times), off-canvas (never inside the frame), unused-keys (after the end,
    outside the layer's time, under an expression or auto layout, or all one value). Read-only. An empty list = nothing
    found; it does not judge how the piece looks (look_frame, look_sheet and look_motion do the seeing)."""
    from .. import diagnose, diagnose_engine      # here: diagnose reads mcp/geometry.py, which this package imports
    doc, comp = doc_and_comp(ctx, args, as_written=True)   # diagnose times it itself and reports a missing marker
    times = markers.times(doc.folder) if doc.folder else None
    found = (diagnose_engine.everything(doc.data, comp["id"], doc.folder, times) if args.get("engine", True)
             else diagnose.problems(comp, doc.folder, times))
    words = "; ".join(f'{p["kind"]}: {p["message"]}' for p in found) or "nothing wrong found"
    return Reply(f'{comp["id"]}: {len(found)} problem(s). {words}', {"comp": comp["id"], "problems": found})
