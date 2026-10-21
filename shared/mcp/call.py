"""Call one tool on a Rostrum MCP server from the command line, over stdio, as an MCP client would.

For agents that can't attach a server to their own session: every call is a real MCP call (handshake, tool
call, reply), so the server records it as `agent:<client name>`. The server opens and saves its document in
the project folder, so calls in a row work on the same document.

    python shared/mcp/call.py --name agent-title -- <server command …> :: look_frame '{"time": 1.2}'
    python shared/mcp/call.py --name agent-title -- <server command …> :: tools        # the tool list

Arguments may be `@args.json` (a file). Prints the reply's JSON; images are saved by the server and listed in `files`. Exit code 1 when ok is false.
"""
from __future__ import annotations

import argparse
import json
import sys

import anyio
from mcp import Client, StdioServerParameters
from mcp_types import Implementation


async def call(server: list[str], name: str, tool: str, args: dict) -> int:
    params = StdioServerParameters(command=server[0], args=server[1:])
    async with Client(params, client_info=Implementation(name=name, version="1")) as client:
        if tool == "tools":
            listed = await client.list_tools()
            for t in listed.tools:
                print(f"{t.name}: {(t.description or '').splitlines()[0] if t.description else ''}")
            return 0
        result = await client.call_tool(tool, args)
        texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
        print("\n".join(texts))
        try:
            return 0 if json.loads(texts[0]).get("ok") else 1
        except (IndexError, ValueError):
            return 1


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")       # replies carry non-ASCII (─, →); Windows consoles default to cp1252
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--" not in argv or "::" not in argv:
        print(__doc__)
        return 2
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--name", default="cli-agent")
    ns = parser.parse_args(argv[:argv.index("--")])
    server = argv[argv.index("--") + 1:argv.index("::")]
    rest = argv[argv.index("::") + 1:]
    tool, raw = rest[0], rest[1] if len(rest) > 1 else "{}"
    if raw.startswith("@"):                     # long arguments (a script's source) from a JSON file
        with open(raw[1:], encoding="utf-8") as f:
            raw = f.read()
    args = json.loads(raw)
    return anyio.run(call, server, ns.name, tool, args)


if __name__ == "__main__":
    sys.exit(main())
