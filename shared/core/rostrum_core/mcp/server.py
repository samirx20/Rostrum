"""The MCP server (stdio) on the official MCP Python SDK: every call is checked, run once, and answered in the one reply shape.

    server = build_server(app, tools)      # app: rostrum_core.mcp.App;  tools: the app's own Tools (optional)
    run_stdio(app, tools)                  # blocks; for a script's `if __name__ == "__main__"`
"""
from __future__ import annotations

import base64
import json
import threading
from pathlib import Path

import anyio
import mcp_types as types
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .. import bug, plugin_parts
from ..errors import RostrumError, codes
from ..who import Who
from . import job_wait, shared_edit, shared_inspect, shared_markers, shared_screen, tools_list
from .context import App, Groups, ToolContext
from .guides import URI
from .jobs import InProcessJobs
from .reply import Reply, error_dict
from .tools import Tools

STANDARD_INSTRUCTIONS = "Read inspect_guide topic 'start-here' first. Replies always carry ok + summary; failures say what is accepted."


class Runtime:
    """Everything one server needs, kept apart from the SDK so tests can call `call()` directly."""

    def __init__(self, app: App, tools: Tools | None = None, jobs=None, groups: Groups | None = None):
        shared = Tools()
        shared_inspect.register(shared)
        shared_edit.register(shared)
        shared_markers.register(shared)
        shared_screen.register(shared)
        tools_list.register(shared)
        self.app, self.tools = app, shared.merged_with(tools) if tools else shared
        if app.script_look:
            shared_edit.with_look(self.tools)
        if app.script_help:
            self.tools.described("run_script", app.script_help)
        self.jobs = jobs or InProcessJobs(log=bug.log)
        self.groups = groups or Groups(used=lambda: {c.session for d in app.documents.values() for c in d.history.changes})
        self._one_at_a_time = threading.Lock()          # one writer: tools never overlap on the document
        self._told = False                              # the first reply said what is open (call)
        self.waited: list = []                          # fn(ctx, args, reply) -> reply, for a job's finished reply (an app's clock)

    def call(self, name: str, args: dict | None, who: Who) -> tuple[dict, list]:
        """Run one tool; the session's first reply starts with what is open and whose (App.opened, agent_start.py)."""
        folder = self.app.folder
        reply, images = self._run(name, args, who)
        if self.app.opened and not self._told:
            self._told = True
            if self.app.folder == folder:                # a first call that switched project says so itself
                reply["summary"] = f"{self.app.opened}\n{reply['summary']}"
        return reply, images

    def _run(self, name: str, args: dict | None, who: Who) -> tuple[dict, list]:
        """Run one tool. Returns (reply dict, images). A failure is `ok: false`, never an exception."""
        try:
            tool = self.tools.get(name)
            args, wait_s = job_wait.take(args, who, job_wait.by_default(name, tool.schema)) if job_wait.ours(tool.schema) else (args, 0)
            checked = tool.check(args)
            group = self.groups.current(who, (args or {}).get("group"))
            ctx = ToolContext(self.app, who, group, self.jobs, name, self.tools)
            with self._one_at_a_time:
                for doc in list(self.app.documents.values()):   # a window may have changed it: read its steps first
                    if getattr(doc, "live", None) is not None:
                        doc.live.catch_up()
                reply = tool.fn(ctx, checked)
            if not isinstance(reply, Reply):
                raise TypeError(f"tool {name} returned {type(reply).__name__}, not Reply")
            done = job_wait.finish(self.jobs, reply, ctx.wait_for[-1] if ctx.wait_for else wait_s, name)   # outside the lock: a job never touches the document
            if done is not reply:                        # the job's finished reply (or how far it got): as inspect_job's
                for fn in self.waited:
                    done = fn(ctx, checked, done)
            reply = done
            said = ctx.notes + [w for d in ctx.seen for w in [*plugin_parts.missing_of(d), *d.kind.warnings(d.data)]]   # never silent (kind.warn, a plugin it lacks)
            reply.warnings.extend(n for n in dict.fromkeys(said) if n not in reply.warnings)
            return reply.to_dict(), reply.images
        except RostrumError as e:
            return error_dict(e.within(name) if not e.where.startswith(name) else e), []
        except Exception as e:                           # a bug: loud, with a log, never a silent success
            return error_dict(bug.internal(name, "", e)), []


def _content(reply: dict, images: list) -> list:
    blocks = [types.TextContent(type="text", text=json.dumps(reply, ensure_ascii=False, indent=1))]
    for img in images:
        raw = Path(img).read_bytes() if isinstance(img, (str, Path)) else bytes(img)
        blocks.append(types.ImageContent(type="image", data=base64.b64encode(raw).decode(), mime_type="image/png"))
    return blocks


def build_server(app: App, tools: Tools | None = None, runtime: Runtime | None = None) -> Server:
    rt = runtime or Runtime(app, tools)

    async def list_tools(ctx, params):
        return types.ListToolsResult(tools=[types.Tool(name=t.name, description=t.description, input_schema=t.schema) for t in rt.tools.all()])

    async def call_tool(ctx, params):
        info = ctx.session.client_params.client_info if ctx.session.client_params else None
        who = Who.agent(info.name if info and info.name else "unknown-agent")
        reply, images = await anyio.to_thread.run_sync(rt.call, params.name, params.arguments, who)
        return types.CallToolResult(content=_content(reply, images), structured_content=reply, is_error=not reply["ok"])

    async def list_resources(ctx, params):
        g = app.guides
        return types.ListResourcesResult(resources=[types.Resource(uri=URI + t, name=t, description=g.title(t), mime_type="text/markdown") for t in g.topics()])

    async def read_resource(ctx, params):
        topic = params.uri.removeprefix(URI) if params.uri.startswith(URI) else None
        if topic is None:
            raise RostrumError(codes.NOT_FOUND, "resources/read", f'"{params.uri}"', "is not a Rostrum resource", [URI + t for t in app.guides.topics()])
        return types.ReadResourceResult(contents=[types.TextResourceContents(uri=params.uri, mime_type="text/markdown", text=app.guides.get(topic))])

    server = Server(app.name, version=app.version, instructions="\n\n".join(t for t in (app.instructions, app.opened, STANDARD_INSTRUCTIONS) if t),
                    on_list_tools=list_tools, on_call_tool=call_tool, on_list_resources=list_resources, on_read_resource=read_resource)
    server.runtime = rt
    return server


async def serve_stdio(app: App, tools: Tools | None = None):
    server = build_server(app, tools)
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())


def run_stdio(app: App, tools: Tools | None = None):
    anyio.run(serve_stdio, app, tools)
