"""run_import: a file (SVG, PDF, PSD, image, video) or a Figma frame into a composition, as one undo step. The screen's Import panel
runs the same code (io/importing.py), so a person and an agent get the same layers and the same report."""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from ..io import importing
from .pick import ITEM_COMP, doc_and_comp

tools = Tools()


@tools.tool("run_import", {"properties": {
    **ITEM_COMP,
    "path": {"type": "string", "description": "The file (absolute, or relative to the project folder). Not for figma."},
    "kind": {"type": "string", "enum": list(importing.KINDS), "description": "Default: from the file's extension (figma: from `figma`)."},
    "page": {"type": "integer", "minimum": 0, "description": "pdf only: the page, counting from 1 (default 1); 0 = every page, each in a new composition (named Page N or the page's label), listed in `comps`."},
    "text": {"type": "string", "enum": ["text", "outline"], "description": "svg only: text as editable text layers (default) or as paths that look exactly like the source."},
    "figma": {"type": "object", "properties": {"key": {"type": "string"}, "frame": {"type": "string"}, "token": {"type": "string"}},
              "required": ["key"], "description": "A Figma frame: the file key, the frame's name (default: the first) and your own token (or set FIGMA_TOKEN). The token is never stored."},
    "into": {"type": "string", "description": "A group's id to import into. Default: the composition."},
    "fit": {"type": "boolean", "description": "svg / pdf (a page) / psd / figma: true = the source's page lands centred in the composition, scaled to fit inside it, under one group. Default false: the source's own size and place."}}})
def run_import(ctx, args):
    """Import a file or a Figma frame into a composition as new layers: svg, pdf (a page, or every page as its own composition), psd, figma → layers with their own names,
    groups and places (text stays text, paths stay paths); an image or a video → one layer, centred, shrunk to fit. One change, all
    or nothing. Returns how many operations ran, the new layer ids and the report: everything that did NOT come across (a PDF mesh
    shading, a font that isn't here, baked effects …). Tell the user what the report says."""
    doc, comp = doc_and_comp(ctx, args)
    path = args.get("path")
    if path and not Path(path).is_absolute():
        path = Path(doc.folder or ".") / path
    try:
        r = importing.run(_Applying(ctx, doc), ctx.who, comp["id"], path, args.get("kind"), args.get("page", 1), args.get("text", "text"),
                          args.get("figma"), args.get("into"), bool(args.get("fit", False)))
    except ValueError as e:                 # a wrong file, kind or id: the caller's to fix, said plainly
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, "the import", str(e)) from None
    say = f'Imported {r["name"]} into {args.get("into") or comp["id"]}: {r["calls"]} operations, {"compositions" if r.get("comps") else "layers"} {", ".join(r.get("comps") or r["layers"])}.'
    say += " Not carried over: " + "; ".join(r["report"]) + "." if r["report"] else " Everything came across."
    return Reply(say, r)


class _Applying:
    """The document, but `apply` records the call group (ctx.apply) like every other tool's change."""

    def __init__(self, ctx, doc):
        self._ctx, self._doc = ctx, doc

    def apply(self, calls, who, label=None):
        return self._ctx.apply(self._doc, calls, label)

    def __getattr__(self, name):
        return getattr(self._doc, name)
