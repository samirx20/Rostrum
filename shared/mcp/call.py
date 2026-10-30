"""Call tools on a Rostrum MCP server from the command line, as an MCP client would, through one long-lived session.

For agents that can't attach a server to their own session: every call is a real MCP call, so the server records it
as `agent:<--name>`. The first command starts a small background session (it starts the server once, ~20 s for 2D);
later commands with the same --name and server command reuse it and answer in about a second. A job started by one
command (a render, a look) is still there for the next. The server opens and saves its document in the project folder.

    python shared/mcp/call.py --name agent-title -- <server command …> :: look_frame '{"time": 1.2}'
    python shared/mcp/call.py --name agent-title -- <server command …> :: tools        # the tools and their arguments
    python shared/mcp/call.py … :: render_video '{"wait": true}'              # waits (up to 50 s) and answers with the file
    python shared/mcp/call.py … :: render_video '{}' :: inspect_job '{"job_id": "JOB", "wait_s": 25}'
    python shared/mcp/call.py --name agent-title -- <server command …> :: stop  # end the session and its server (once its jobs end)

Several `:: tool args` in a row run in order. `JOB` in a later call's arguments is replaced by the last reply's job id
(in the same command). Arguments may be `@args.json` (a file; a relative path is from the current folder). Every
look_* and render_* tool takes `"wait": true` (up to 50 s, or a number of seconds up to 600): it waits for its job and answers
with the finished file; past the wait the reply says the job is still running and gives its job_id. Prints each
reply's JSON; images are saved by the server and listed in `files`. The calls stop at the first reply whose ok is
false: the later ones are NOT run (a render must never run on a document the failed step did not change), the output
says which step failed and which were skipped, and the exit code is 1.

Options before `--`:
    --name NAME       the client name the server records (`agent:NAME`). Default cli-agent.
    --session KEY     the session to use. Default: made from --name, the server command, the current folder and the
                      ROSTRUM* / PYTHONPATH environment (the server runs with the environment that started it).
                      With a running --session the server command may be left out (`call.py --session KEY :: tool …`).
    --stop            end the session and its server (same as a last `:: stop`); a job still running finishes first.
    --once            no session: start the server for this command only and end it after (jobs end with it).

A session ends itself after 30 min with no call (ROSTRUM_CALL_IDLE_S), but never while its server has a job waiting or
running, and when its server ends. A job outlives its session's end: after a stop or the idle end, inspect_job with its
id in the next session reads it (running, then its result). If the session died (killed, the server crashed), the next
command says so, starts a fresh one, and tells you that jobs started in the old one are gone.
Sessions are listed in <ROSTRUM_DATA or ~/.rostrum>/call-sessions/ (one .json each, plus its .log).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

START_S = 180                                      # a server's start-up (2D ~20 s; a cold disk much more)


def folder() -> Path:
    return Path(os.environ.get("ROSTRUM_DATA") or Path.home() / ".rostrum") / "call-sessions"


def session_key(name: str, server: list[str]) -> str:
    env = sorted((k, v) for k, v in os.environ.items() if k.upper().startswith("ROSTRUM") or k.upper() == "PYTHONPATH")
    digest = hashlib.sha1(json.dumps([name, server, os.getcwd(), env]).encode()).hexdigest()[:10]
    return f"{re.sub(r'[^A-Za-z0-9_.-]', '_', name)[:40]}-{digest}"


class Session:
    """A connection to a running session process (call_session.py)."""

    def __init__(self, record: dict):
        self.record = record
        self.sock = socket.create_connection(("127.0.0.1", record["port"]), timeout=3)
        self.sock.settimeout(None)                 # a call may wait for its job for minutes
        self.file = self.sock.makefile("rb")

    def ask(self, req: dict) -> dict:
        self.sock.sendall((json.dumps({**req, "token": self.record["token"]}) + "\n").encode("utf-8"))
        line = self.file.readline()
        if not line:
            pid = self.record["pid"]
            raise SystemExit(f"*** The session (process {pid}) ended during this call; its server and jobs are gone. "
                             f"Its log: {folder() / (self.record['key'] + '.log')}. The next command starts a fresh session.")
        return json.loads(line)


def _read(path: Path) -> dict | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _connect(record: dict | None) -> Session | None:
    if not record:
        return None
    try:
        return Session(record)
    except OSError:
        return None


def _start(key: str, name: str, server: list[str]) -> Session:
    d = folder()
    d.mkdir(parents=True, exist_ok=True)
    rec, log = d / f"{key}.json", d / f"{key}.log"
    rec.unlink(missing_ok=True)
    flags = 0
    if os.name == "nt":                            # its own process, no window, outliving this command
        flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.CREATE_NO_WINDOW | 0x01000000   # BREAKAWAY_FROM_JOB
    cmd = [sys.executable, str(Path(__file__).with_name("call_session.py")), str(rec), name, json.dumps(server)]
    with open(log, "w", encoding="utf-8") as out:
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=out, creationflags=flags,
                                    start_new_session=os.name != "nt")
        except OSError:                            # a job that forbids breaking away: start inside it
            proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=out,
                                    creationflags=flags & ~0x01000000)
    until = time.monotonic() + START_S
    while time.monotonic() < until:
        record = _read(rec)
        if record and (s := _connect({**record, "key": key})):
            return s
        if proc.poll() is not None:
            break
        time.sleep(0.2)
    tail = log.read_text(encoding="utf-8", errors="replace")[-3000:] if log.exists() else ""
    if proc.poll() is None:
        proc.kill()                                # our own child, by its handle
    raise SystemExit(f"*** The session could not start the server ({' '.join(server)}) within {START_S} s. "
                     f"Log {log}:\n{tail}")


def open_session(key: str, name: str, server: list[str] | None) -> Session:
    rec = folder() / f"{key}.json"
    record = _read(rec)
    if record:
        record["key"] = key
        if server and (record.get("server") != server or record.get("name") != name):
            raise SystemExit(f"*** Session {key} runs `{' '.join(record['server'])}` as {record['name']}, not this server/name. "
                             "End it first (:: stop) or use another --session.")
        if s := _connect(record):
            return s
        print(f"*** Session {key} (process {record.get('pid')}) is gone (it ended or died). Starting a fresh one: "
              "jobs started in the old session are gone; start them again.", flush=True)
        server = server or record.get("server")
    if not server:
        raise SystemExit(f"*** No session {key} is running; give the server command after `--` to start one.")
    return _start(key, name, server)


def stop(key: str) -> int:
    record = _read(folder() / f"{key}.json")
    s = _connect({**record, "key": key} if record else None)
    if not s:
        print(f"No session {key} is running.")
        return 0
    running = s.ask({"op": "stop"}).get("running", 0)   # its record is gone by the reply: it takes no more calls
    if running:
        print(f"Session {key} takes no more calls; it ends (process {record['pid']}) with its server once its {running} "
              "running job(s) end. inspect_job with a job's id in a new session reads it, then its result.")
    else:
        print(f"Session {key} ended (process {record['pid']}) with its server.")
    return 0


def run(ask, calls: list[tuple[str, dict]], stopping) -> int:
    job = None
    for n, (tool, args) in enumerate(calls, 1):
        if tool == "stop":
            return stopping()
        if tool == "tools":
            for t in ask({"op": "tools"})["tools"]:
                print(f"{t['name']}({', '.join(t['args'])}): {t['first']}")
            continue
        if job:
            args = json.loads(json.dumps(args).replace('"JOB"', json.dumps(job)))
        got = ask({"op": "call", "tool": tool, "args": args})
        if "error" in got:
            print(f"*** {got['error']}. The session ended; the next command starts a fresh one (jobs from this one are gone).")
            return 1
        texts = got["texts"]
        print("\n".join(texts))
        try:
            reply = json.loads(texts[0])
        except (IndexError, ValueError):
            reply = {"ok": False}
        if not reply.get("ok"):
            left = [f"{i}. {t}" for i, (t, _) in enumerate(calls[n:], n + 1)]
            print(f"*** STOPPED: step {n} ({tool}) failed." + (f" NOT run: {', '.join(left)}." if left else " It was the last step."))
            return 1
        job = (reply.get("data") or {}).get("job_id") or job
    return 0


def once(server: list[str], name: str, calls: list[tuple[str, dict]]) -> int:
    """--once: the server lives for this command only (the old way)."""
    import anyio
    from mcp import Client, StdioServerParameters
    from mcp_types import Implementation

    sys.path.insert(0, str(Path(__file__).parent))
    import call_session

    async def go():                                 # run() is plain code: it runs in a thread, asking this loop
        params = StdioServerParameters(command=server[0], args=server[1:], env=dict(os.environ))
        async with Client(params, client_info=Implementation(name=name, version="1")) as client:
            ask = lambda req: anyio.from_thread.run(call_session._answer, client, req)   # noqa: E731
            return await anyio.to_thread.run_sync(lambda: run(ask, calls, lambda: 0))
    return anyio.run(go)


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
    head_end = min((argv.index(m) for m in ("--", "::") if m in argv), default=len(argv))
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--name", default="cli-agent")
    parser.add_argument("--session")
    parser.add_argument("--stop", action="store_true")
    parser.add_argument("--once", action="store_true")
    ns = parser.parse_args(argv[:head_end])
    server = argv[argv.index("--") + 1:argv.index("::") if "::" in argv else len(argv)] if "--" in argv else []
    if not ("::" in argv or ns.stop) or not (server or ns.session):
        print(__doc__)
        return 2
    calls, rest = [], argv[argv.index("::"):] if "::" in argv else []
    while rest and rest[0] == "::":
        tool, rest = rest[1], rest[2:]
        raw = rest.pop(0) if rest and rest[0] != "::" else "{}"
        calls.append((tool, _args(raw)))
    if ns.stop:
        calls.append(("stop", {}))
    if ns.once:
        return once(server, ns.name, [c for c in calls if c[0] != "stop"])
    key = ns.session or session_key(ns.name, server)
    if calls and calls[0][0] == "stop":
        return stop(key)
    s = open_session(key, ns.name, server or None)
    return run(s.ask, calls, lambda: stop(key))


if __name__ == "__main__":
    sys.exit(main())
