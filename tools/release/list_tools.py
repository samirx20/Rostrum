"""Start an MCP server exactly as an agent would (stdio), do the handshake and list its tools. For the installer walk.

    <installed python.exe> list_tools.py <command> [args …]
    <installed python.exe> list_tools.py --codex <config.toml> <server name>    the command and args that file holds

Prints the server's name and its tool count, then the tool names; exits 1 when the server doesn't start or lists none.
"""
from __future__ import annotations

import sys
import tomllib

import anyio
from mcp import Client, StdioServerParameters


async def tools(command: str, args: list[str], env: dict | None) -> list[str]:
    async with Client(StdioServerParameters(command=command, args=args, env=env)) as c:
        return [t.name for t in (await c.list_tools()).tools]


def main(argv: list[str]) -> int:
    env = None
    if argv[0] == "--codex":
        with open(argv[1], "rb") as f:
            entry = tomllib.load(f)["mcp_servers"][argv[2]]
        command, args = entry["command"], list(entry.get("args", []))
        env = {**__import__("os").environ, **entry.get("env", {})}
    else:
        command, args = argv[0], argv[1:]
    print("starting:", command, *args)
    names = anyio.run(tools, command, args, env)
    print(f"{len(names)} tools:", ", ".join(names))
    return 0 if names else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
