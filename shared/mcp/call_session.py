"""The background half of call.py: one long-lived MCP client session to one server, so calls from later commands reuse
it (no server start-up each time) and a job started by one command is still there for the next.

    python call_session.py <record.json> <client name> <server command as JSON>

Started detached by call.py, never by hand. It starts the server over stdio as an MCP client named <client name> (the
server records every call as `agent:<client name>`), listens on a localhost port, and writes <record.json>
({pid, port, token, name, server, cwd}) once the server is ready. One request at a time, one JSON line each way:

    {"token", "op": "call", "tool", "args"}  ->  {"texts": [...]}        a tool's reply (its text blocks)
    {"token", "op": "tools"}                 ->  {"tools": [{"name", "args", "first"}]}
    {"token", "op": "stop"}                  ->  {"stopped": true, "running": n}   ends the server and this process
    anything failing                         ->  {"error": "..."}

It ends itself after ROSTRUM_CALL_IDLE_S seconds (default 1800) with no request, and when the server ends; either
way it removes its record, so the next call.py starts a fresh one and says so. A job the server has waiting or running
keeps it: no idle end while one runs, and a stop with jobs running takes no more calls (its record goes at once) but
keeps the server until they end. Ending the client would end the server and its jobs (the SDK ends the server's
process tree), which lost a showreel export at frame 562 of 2400 (2026-10-28). Their ends stay in the job files, so
inspect_job in the next session reads them (rostrum_core/mcp/job_files.py; the server tags its job files with
ROSTRUM_CALL_SESSION, this session's key).
"""
from __future__ import annotations

import json
import os
import secrets
import sys
import time
from pathlib import Path

import anyio
from mcp import Client, StdioServerParameters
from mcp_types import Implementation

IDLE_S = float(os.environ.get("ROSTRUM_CALL_IDLE_S", "1800"))
DRAIN_POLL_S = 1.0


def live_jobs(key: str) -> int:
    """The server's jobs waiting or running now, from their files (job_files.py writes them with our key)."""
    d = Path(os.environ.get("ROSTRUM_DATA") or Path.home() / ".rostrum") / "jobs"
    n = 0
    for p in d.glob("*.json") if d.is_dir() else []:
        try:
            state = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        n += state.get("session") == key and state.get("status") in ("queued", "running")
    return n


async def _answer(client: Client, req: dict) -> dict:
    if req.get("op") == "tools":
        out = []
        for t in (await client.list_tools()).tools:
            first = (t.description or "").splitlines()[0] if t.description else ""
            out.append({"name": t.name, "args": list((t.input_schema or {}).get("properties", {})), "first": first})
        return {"tools": out}
    result = await client.call_tool(req["tool"], req.get("args") or {})
    return {"texts": [c.text for c in result.content if getattr(c, "type", "") == "text"]}


async def serve(record: Path, name: str, server: list[str]) -> None:
    token, busy, last, key = secrets.token_hex(16), anyio.Lock(), [time.monotonic()], record.stem
    env = {**os.environ, "ROSTRUM_CALL_SESSION": key}   # the caller's environment (the SDK passes only a few names)
    params = StdioServerParameters(command=server[0], args=server[1:], cwd=os.getcwd(), env=env)
    async with Client(params, client_info=Implementation(name=name, version="1")) as client, anyio.create_task_group() as tg:
        listener = await anyio.create_tcp_listener(local_host="127.0.0.1", local_port=0)
        port = listener.extra(anyio.abc.SocketAttribute.local_port)
        listening = anyio.CancelScope()

        async def end():
            """End once the server's jobs have ended (none: at once); meanwhile no new calls."""
            listening.cancel()
            record.unlink(missing_ok=True)
            while (n := live_jobs(key)):
                print(f"call_session: ending once {n} job(s) end", file=sys.stderr, flush=True)
                await anyio.sleep(DRAIN_POLL_S)
            tg.cancel_scope.cancel()

        async def listen():
            with listening:
                await listener.serve(handle)

        async def handle(stream):
            async with stream:
                buf = b""
                while True:
                    try:
                        chunk = await stream.receive()
                    except (anyio.EndOfStream, anyio.BrokenResourceError):
                        return
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        req = json.loads(line)
                        if req.get("token") != token:
                            return                               # not our caller
                        async with busy:                         # one call at a time on the one session
                            last[0] = time.monotonic()
                            if req.get("op") == "stop":
                                await stream.send((json.dumps({"stopped": True, "running": live_jobs(key)}) + "\n").encode())
                                tg.start_soon(end)
                                return
                            try:
                                reply = await _answer(client, req)
                            except Exception as e:               # noqa: BLE001  the server failed or ended: say so, then end
                                await stream.send((json.dumps({"error": f"the server failed: {type(e).__name__}: {e}"}) + "\n").encode())
                                tg.cancel_scope.cancel()
                                return
                            last[0] = time.monotonic()
                        await stream.send((json.dumps(reply, ensure_ascii=False) + "\n").encode("utf-8"))

        async def idle():
            while True:
                await anyio.sleep(min(30.0, IDLE_S / 4))
                if not busy.locked() and time.monotonic() - last[0] > IDLE_S and not live_jobs(key):
                    print(f"call_session: idle {IDLE_S:g} s, ending", file=sys.stderr, flush=True)
                    tg.cancel_scope.cancel()

        tg.start_soon(listen)
        tg.start_soon(idle)
        tmp = record.with_suffix(".tmp")
        tmp.write_text(json.dumps({"pid": os.getpid(), "port": port, "token": token, "name": name, "server": server,
                                   "cwd": os.getcwd(), "started": time.time()}), encoding="utf-8")
        tmp.replace(record)                                      # whole, once the server answered the handshake


def main() -> None:
    record, name, server = Path(sys.argv[1]), sys.argv[2], json.loads(sys.argv[3])
    try:
        anyio.run(serve, record, name, server)
    finally:
        try:
            if json.loads(record.read_text(encoding="utf-8")).get("pid") == os.getpid():
                record.unlink()
        except (OSError, ValueError):
            pass
        print("call_session: ended", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
