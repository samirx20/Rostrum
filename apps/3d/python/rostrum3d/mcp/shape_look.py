"""look_shape: an item's form, not a lit picture: its outlines from the front, the side and the top (one PNG, three
panels on one scale) and its measures in numbers (rostrum3d.shape_measure)."""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools
from rostrum_core.mcp.files import look_path

from rostrum3d import clay_detail, ops_mesh, ops_pose, pose_joints as PJ, shape_measure as SM

from . import draw, shape_picture

tools = Tools()
CELLS = 128                    # the clay grid's cells along its longest side
THIN_GRAINS, THIN_CELLS = 4, 3     # thinner than this many grains (or grid cells) is a thin spot


def length(m: float) -> str:
    """'38 cm', '1.24 m', '6 mm': a length in plain words."""
    if abs(m) >= 1:
        return f"{m:.2f} m"
    return f"{m * 100:.0f} cm" if abs(m) >= 0.1 else f"{m * 100:.1f} cm" if abs(m) >= 0.01 else f"{m * 1000:.0f} mm"


def _clay(ctx, doc, item, cells):
    if ops_pose._GRID is None:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, item["id"], "has no engine to read its clay from")
    try:
        grid = ops_pose._GRID(doc.data, item["id"], cells)
    except Exception as e:  # noqa: BLE001  the core's refusal, named
        raise RostrumError(codes.RENDER_FAILED, ctx.tool, f'clay "{item["id"]}"', f"could not be sampled: {e}") from e
    occ = PJ.occupancy(grid)
    views = SM.from_grid(occ, grid["origin"], grid["cell"])
    grain = clay_detail.detail(doc.data, item, ctx.app.folder)
    thin = max(THIN_GRAINS * grain, THIN_CELLS * float(grid["cell"]))
    return views, SM.thin_spots(occ, grid["origin"], float(grid["cell"]), thin), thin


def _mesh(ctx, doc, item):
    try:
        g = ops_mesh._GEOMETRY(doc.data, item["id"])
    except Exception as e:  # noqa: BLE001
        raise RostrumError(codes.RENDER_FAILED, ctx.tool, f'"{item["id"]}"', f"its mesh could not be read: {e}") from e
    pts = g["points"]
    pts = [pts[i:i + 3] for i in range(0, len(pts), 3)] if pts and not isinstance(pts[0], list) else pts
    tris, at = [], 0
    for n in g["faceCounts"]:
        f = g["faceIndices"][at:at + n]
        tris += [(f[0], f[k], f[k + 1]) for k in range(1, n - 1)]
        at += n
    if not tris:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"{item["id"]}"', "has no faces to measure")
    return SM.from_triangles(pts, tris), None, None


def _words(item, m, thin_spots, thin) -> str:
    h = m["height"]
    lv = "; ".join(f'{r["percent"]} % {length(r["width"])}' + (f' ({r["parts"]} parts)' if r["parts"] > 1 else "")
                   for r in m["levels"])
    sym = m["mirror"]
    mirrored = item.get("symmetry") == "x"
    if sym["worst"] == 0:
        lr = "left and right match" + (" (it is mirrored)" if mirrored else "")
    else:
        lr = (f'left and right differ by up to {length(sym["worst"])} at {sym["worstPercent"]} % height '
              f'(from {sym["offFrom"]} to {sym["offTo"]} %; {sym["differs"]} % of the front outline)'
              + (", though it is mirrored: a carve, a stroke or a step with Mirror off" if mirrored else ""))
    if thin is None:
        th = "thin spots are measured on clay only"
    elif not thin_spots:
        th = f"no spot thinner than {length(thin)}"
    else:
        th = (f"{len(thin_spots)} thin spot{'s' if len(thin_spots) > 1 else ''} (under {length(thin)}): "
              + ", ".join(f'{length(s["thickness"])} at {round(100 * (s["at"][1] - m["low"][1]) / h)} % height'
                          f'{" " + s["side"] if s.get("side") else ""}' for s in thin_spots))
    return (f'{length(h)} tall, {length(m["width"])} wide, {length(m["depth"])} deep; widest {length(m["widest"]["width"])} '
            f'at {m["widest"]["percent"]} % height. Widths from the front: {lv}. {lr[0].upper() + lr[1:]}; {th}.')


@tools.tool("look_shape", {"required": ["target"], "properties": {
    "item": {"type": "string", "description": "The document's project item id. Optional when only one document is open."},
    "target": {"type": "string", "description": "The id of the clay or mesh to measure."},
    "cells": {"type": "integer", "minimum": 24, "maximum": 128, "default": CELLS,
              "description": "A clay: how finely it is sampled along its longest side (more: finer outlines and thin spots, slower)."}}})
def look_shape(ctx, args):
    """An item's FORM, not a lit picture: its outlines from the front (+Z, its left on the picture's right), the side (from its left,
    +X: its front faces left) and the top (its front down), on one scale with a scale bar and lines at each tenth of its height;
    plus its measures in numbers, in its own space (metres, before the item's scale): height, width, depth, the width and depth at
    10 %, 20 % … 90 % of its height (and in how many parts it is cut there: two legs = 2), the widest, the left-right difference
    (the front outline against its mirror across its own X = 0, where it is off) and, on a clay, thin spots (where its middle is
    thinner than ~4 grains: a fragile neck, a wrist that will break up). A clay is measured from its rest shape (the pose isn't
    measured); a mesh from its built mesh. Use it to check proportions and symmetry in numbers after building, before lighting."""
    doc = ctx.document(args.get("item"))
    item = doc.item(args["target"]) if doc.has(args["target"]) else None
    if item is None or item.get("type") not in ("clay", "mesh", "combine"):
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'target "{args["target"]}"',
                           "is not a clay or a mesh" if item else "is not an item of this document",
                           sorted(i["id"] for i in doc.items() if i.get("type") in ("clay", "mesh", "combine")))
    engine = draw.engine_of(ctx)
    dest = look_path(f'{doc.item_id or "doc"}_{item["id"]}_shape', project=doc.folder)

    def job_fn(job):
        if item["type"] == "clay":
            views, spots, thin = _clay(ctx, doc, item, args.get("cells", CELLS))
        else:
            views, spots, thin = _mesh(ctx, doc, item)
        m = SM.measure(views)
        for s in spots or []:
            s["percent"] = round(100 * (s["at"][1] - m["low"][1]) / m["height"])
            s["side"] = "" if abs(s["at"][0]) < 1.5 * m["cell"] else ("left" if s["at"][0] > 0 else "right")
        shape_picture.draw(views, m, spots or [], dest, item.get("name") or item["id"])
        rest = " Measured at rest (its pose isn't)." if item["type"] == "clay" and item.get("bones") else ""
        data = {"target": item["id"], "space": "own", **m,
                "thinSpots": spots, "thin": thin, "mirrored": item.get("symmetry") == "x"}
        return Reply(f'{item["id"]}: ' + _words(item, m, spots, thin) + rest, data, [dest], [dest], engine.take_notices())

    return ctx.long(f'look_shape {item["id"]}', job_fn)
