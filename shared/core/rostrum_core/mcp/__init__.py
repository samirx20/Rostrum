"""MCP plumbing for every Rostrum app (contract: shared/mcp/CONVENTIONS.md). Needs the `mcp` extra.

Each name loads its module on first use (PEP 562): the screens import plain helpers from here (files.RENDER_DIR) at
start, and the MCP SDK under `server` costs over a second to import, so a window never pays for a server it doesn't run.
"""
from importlib import import_module

_FROM = {"App": "context", "Groups": "context", "ToolContext": "context", "Guides": "guides",
         "InProcessJobs": "jobs", "Job": "jobs", "Jobs": "jobs", "Reply": "reply", "error_dict": "reply",
         "Runtime": "server", "build_server": "server", "run_stdio": "server", "serve_stdio": "server",
         "Tool": "tools", "Tools": "tools", "default_tools": "tools", "tool": "tools"}
__all__ = list(_FROM)


def __getattr__(name):
    if name not in _FROM:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    return getattr(import_module(f".{_FROM[name]}", __name__), name)
