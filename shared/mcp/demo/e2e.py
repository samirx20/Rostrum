"""End-to-end demo (not a test): start rostrum-toy over stdio, edit the document, read the history back.

Run:  python shared/mcp/demo/e2e.py   (with the worktree's .venv python)
Prints the history entry's `who`: kind "agent" and this client's name, as the MCP handshake gave it.
"""
import json
import sys
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters
from mcp_types import Implementation

SERVER = Path(__file__).with_name("toy_server.py")


async def main():
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with Client(params, client_info=Implementation(name="e2e-demo-client", version="1")) as client:
        edit = await client.call_tool("edit_document", {"ops": [{"op": "layer.move", "target": ["card"], "args": {"x": 400}}]})
        print("edit_document:", json.loads(edit.content[0].text)["summary"])
        hist = json.loads((await client.call_tool("inspect_history", {})).content[0].text)
        who = hist["data"]["changes"][-1]["who"]
        print("history who:", who)
        assert who["kind"] == "agent" and who["name"] == "e2e-demo-client", who
        print("OK: the change is recorded as agent:e2e-demo-client")


anyio.run(main)
