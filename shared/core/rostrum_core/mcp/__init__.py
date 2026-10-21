"""MCP plumbing for every Rostrum app (contract: shared/mcp/CONVENTIONS.md). Needs the `mcp` extra."""
from .context import App, Groups, ToolContext
from .guides import Guides
from .jobs import InProcessJobs, Job, Jobs
from .reply import Reply, error_dict
from .server import Runtime, build_server, run_stdio, serve_stdio
from .tools import Tool, Tools, default_tools, tool

__all__ = ["App", "Groups", "ToolContext", "Guides", "InProcessJobs", "Job", "Jobs", "Reply", "error_dict",
           "Runtime", "build_server", "run_stdio", "serve_stdio", "Tool", "Tools", "default_tools", "tool"]
