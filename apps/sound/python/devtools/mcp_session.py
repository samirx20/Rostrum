"""A plain MCP client for agents without the server attached: runs a list of tool calls against `rostrum-sound`
over stdio, in one session, and prints each reply. Only MCP goes over the wire; nothing is imported from the app.

    python devtools/mcp_session.py --folder <project folder> calls.json [--item cue] [--client my-agent]

calls.json: [{"tool": "run_script", "arguments": {...}}, ...]. A reply that is a job (data.job_id) is followed by
inspect_job until the job ends. Pictures the server sends are listed by their file paths in each reply.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters
from mcp_types import Implementation


async def session(folder: str, items: list[str], calls: list[dict], client: str):
    args = ["-m", "rostrum_sound.mcp.server", "--folder", folder] + [a for i in items for a in ("--item", i)]
    params = StdioServerParameters(command=sys.executable, args=args)
    failed = 0
    async with Client(params, client_info=Implementation(name=client, version="1")) as c:
        for n, call in enumerate(calls, 1):
            reply = json.loads((await c.call_tool(call["tool"], call.get("arguments", {}))).content[0].text)
            job = reply.get("data", {}).get("job_id") if reply.get("ok") else None
            while job and reply.get("data", {}).get("status") in ("queued", "running"):
                reply = json.loads((await c.call_tool("inspect_job", {"job_id": job, "wait_s": 20})).content[0].text)
            failed += not reply.get("ok")
            print(f"--- {n}. {call['tool']}\n{json.dumps(reply, indent=1, ensure_ascii=False)[:6000]}", flush=True)
    return failed


def main():
    sys.stdout.reconfigure(encoding="utf-8")       # replies hold en dashes and arrows; a Windows console is not UTF-8
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("calls")
    p.add_argument("--folder", required=True)
    p.add_argument("--item", action="append")
    p.add_argument("--client", default="mcp-session")
    a = p.parse_args()
    calls = json.loads(Path(a.calls).read_text(encoding="utf-8"))
    failed = anyio.run(session, a.folder, a.item or ["cue"], calls, a.client)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
