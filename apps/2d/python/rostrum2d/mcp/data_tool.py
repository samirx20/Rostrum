"""inspect_table: a data file read as rows, for a chart or one design -> many videos (a script can't open files;
rostrum2d/table.py, guides/data-math-and-graphs.md)."""
from __future__ import annotations

from pathlib import Path

from rostrum_core.errors import RostrumError, codes
from rostrum_core.mcp import Reply, Tools

from ..plot import nice_ticks
from ..table import columns, read_table

tools = Tools()


@tools.tool("inspect_table", {"required": ["path"], "properties": {
    "path": {"type": "string", "description": "The file: .csv, .tsv, .txt (comma, tab or semicolon between cells, a header row first) or .json (a list of objects). Absolute, or relative to the project folder."},
    "rows": {"type": "integer", "minimum": 1, "description": "Return at most this many rows (default 500); the reply says how many the file has."}}})
def inspect_table(ctx, args):
    """Read a table of data from a file, as rows to paste into run_script (a script can't open files): one object per
    row keyed by the header, number cells already numbers. Each number column comes with its min, max and round axis
    ticks (`ticks`, steps of 1, 2 or 5 × a power of ten, from 0 (or the min, when below 0) to past the max; the script's nice_ticks gives the
    same). Use it for a chart from data, or to loop over the rows and make one composition per row (one design ->
    many videos, then render_export each comp). Guide: inspect_guide 'data-math-and-graphs'."""
    path = Path(args["path"])
    if not path.is_absolute():
        path = Path(ctx.app.folder or ".") / path
    if not path.is_file():
        raise RostrumError(codes.NOT_FOUND, ctx.tool, f'"{path}"', "is not a file", ["a .csv, .tsv, .txt or .json file"])
    try:
        rows = read_table(path)
    except (ValueError, UnicodeDecodeError) as e:
        raise RostrumError(codes.BAD_ARGUMENT, ctx.tool, f'"{path.name}"', str(e)) from None
    cols = columns(rows)
    for c in cols:
        if "min" in c:
            c["ticks"] = nice_ticks(min(c["min"], 0), c["max"], extend=True)
    limit = int(args.get("rows", 500))
    words = (f"{len(rows)} row{'s' if len(rows) != 1 else ''}, columns: {', '.join(c['name'] for c in cols)}"
             + (f"; showing the first {limit}" if len(rows) > limit else ""))
    return Reply(words, {"file": str(path), "count": len(rows), "columns": cols, "rows": rows[:limit]})
