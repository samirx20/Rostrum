"""The rostrum-2d MCP server: the 2D tools on top of rostrum_core.mcp. Needs the `mcp` extra (pip install rostrum2d[mcp]).

The server (and the MCP SDK under it, over a second to import) loads on first use of `app_tools` / `main` /
`make_app`: the screen imports this package's plain helpers (exporting, export_name) at start and never the server.
"""
__all__ = ["app_tools", "main", "make_app"]


def __getattr__(name):
    if name not in __all__:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from . import server
    return getattr(server, name)
