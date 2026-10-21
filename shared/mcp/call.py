"""Call one tool on a Rostrum MCP server from the command line, over stdio, as an MCP client would.

For agents that can't attach a server to their own session: every call is a real MCP call (handshake, tool
call, reply), so the server records it as `agent:<client name>`. The server opens and saves its document in
the project folder, so calls in a row work on the same document.

    python shared/mcp/call.py --name agent-title -- <server command …> :: look_frame '{"time": 1.2}'
    python shared/mcp/call.py --name agent-title -- <server command …> :: tools        # the tools and their arguments
    python shared/mcp/call.py … :: render_video '{}' :: inspect_job '{"job_id": "JOB", "wait_s": 25}'   # one session

Several `:: tool args` in a row run in ONE session (one server process): a long job started by one call can be
waited on by the next (jobs end with their server). `JOB` in a later call's arguments is replaced by the last
reply's job id. Arguments may be `@args.json` (a file; a relative path is from the current folder). Prints each
reply's JSON; images are saved by the server and listed in `files`. Exit code 1 when any reply's ok is false.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters
from mcp_types import Implementation


async def call(server: list[str], name: str, calls: list[tuple[str, dict]]) -> int:
    params = StdioServerParameters(command=server[0], args=server[1:])
    code, job = 0, None
    async with Client(params, client_info=Implementation(name=name, version="1")) as client:
        for tool, args in calls:
            if tool == "tools":
                for t in (await client.list_tools()).tools:
                    props = (t.input_schema or {}).get("properties", {})
                    first = (t.description or "").splitlines()[0] if t.description else ""
                    print(f"{t.name}({', '.join(props)}): {first}")
                continue
            if job:
                args = json.loads(json.dumps(args).replace('"JOB"', json.dumps(job)))
            result = await client.call_tool(tool, args)
            texts = [c.text for c in result.content if getattr(c, "type", "") == "text"]
            print("\n".join(texts))
            try:
                reply = json.loads(texts[0])
            except (IndexError, ValueError):
                code = 1
                continue
            code = code or (0 if reply.get("ok") else 1)
            job = (reply.get("data") or {}).get("job_id") or job
    return code


def _args(raw: str) -> dict:
    if raw.startswith("@"):                     # long arguments (a script's source) from a JSON file
        path = Path(raw[1:]).resolve()
        if not path.is_file():
            raise SystemExit(f"call.py: no arguments file {path} (a relative @path is from {Path.cwd()})")
        raw = path.read_text(encoding="utf-8")
    return json.loads(raw)


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
    calls, rest = [], argv[argv.index("::"):]
    while rest and rest[0] == "::":
        tool, rest = rest[1], rest[2:]
        raw = rest.pop(0) if rest and rest[0] != "::" else "{}"
        calls.append((tool, _args(raw)))
    return anyio.run(call, server, ns.name, calls)


if __name__ == "__main__":
    sys.exit(main())
