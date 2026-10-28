"""inspect_asset_sources, inspect_assets and edit_import_asset: the asset library for agents (rostrum3d/assets).
Every source is off until the person switches it on in Import › Asset library; these tools can't switch one on, and
fail plainly while it is off. A model's files are downloaded into the project folder only on edit_import_asset.
"""
from __future__ import annotations

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from rostrum3d import assets

tools = Tools()
SOURCE = {"type": "string", "description": "The source's id (what \"sources\" lists them)."}


def _fail(ctx, subject: str, e: assets.AssetError):
    raise RostrumError(codes.BAD_ARGUMENT if e.off else codes.JOB_FAILED, ctx.tool, subject, str(e),
                       hint="Tell the person; only they can switch a source on." if e.off else None) from None


@tools.tool("inspect_asset_sources", {"properties": {}})
def asset_sources(ctx, args):
    """The sources: id, licence, site, on or off (only the person switches one on)."""
    rows = [assets.facts(s) for s in assets.sources()]
    lines = [f'{r["name"]} ({r["id"]}, {r["licence"]}, {r["site"]}): {"on" if r["on"] else "off"}' for r in rows]
    return Reply("Asset sources: " + "; ".join(lines) + ("." if any(r["on"] for r in rows) else
                 ". All are off; the person switches one on in Import › Asset library."), {"sources": rows})


@tools.tool("inspect_assets", {"required": ["source"], "properties": {
    "source": SOURCE,
    "query": {"type": "string", "default": "", "description": "Words that must all match name or tags; empty lists all."},
    "page": {"type": "integer", "minimum": 0, "default": 0, "description": "Which page of 40 results (0 first)."}}})
def asset_search(ctx, args):
    """Search a switched-on source's models (id, name, thumbnail); nothing is downloaded."""
    try:
        found = assets.search(args["source"], args.get("query", ""), args.get("page", 0))
    except assets.AssetError as e:
        _fail(ctx, f'source "{args["source"]}"', e)
    shown = ", ".join(f'{m["name"]} ({m["id"]})' for m in found[:12])
    return Reply(f'{len(found)} model(s) on this page' + (f": {shown}" + (" …" if len(found) > 12 else "") if found else
                 "; try other words or page 0.") + ".", {"models": found})


@tools.tool("edit_import_asset", {"required": ["source", "id"], "properties": {
    "source": SOURCE,
    "id": {"type": "string", "description": "The model's id (what \"search\" finds it)."},
    "item": {"type": "string", "description": "The document's item id; optional with one document open."},
    **{k: {"type": "number", "default": 0, "description": f"The base's {k} in metres."} for k in "xyz"}}})
def asset_import(ctx, args):
    """Download a model into the project and import it, its base at x y z (default; one undo step)."""
    doc = ctx.document(args.get("item"))
    try:
        src = assets.source(args["source"])
        found = assets.bring_in(src.id, args["id"], ctx.app.folder or doc.folder)
    except assets.AssetError as e:
        _fail(ctx, f'model "{args["id"]}"', e)
    before = {i["id"] for i in doc.data.get("items", [])}
    call = {"op": "import.add", "args": {"file": str(found), "name": args["id"], **{k: float(args.get(k, 0)) for k in "xyz"}}}
    change = ctx.apply(doc, [call], f'Import {args["id"]} from {src.name}')
    new = [i["id"] for i in doc.data.get("items", []) if i["id"] not in before]
    return Reply(f'Imported {args["id"]} from {src.name} ({src.licence}) as {new[0] if new else "an import"}; its files are in {found.parent}.',
                 {"item": new[0] if new else None, "file": str(found), "seq": change.seq if change else doc.seq})
