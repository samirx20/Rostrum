"""(Copy of proofs/2d-character/mcp_session.py; project and item from ROSTRUM_PROJECT / ROSTRUM_ITEM.)
Drive the rostrum-2d MCP server over stdio (the only way this proof touches the document).
    python mcp_session.py calls.json      calls = [{"tool": ..., "args": {...}}, ...]
Jobs (look_frame, render_video ...) are waited for with inspect_job. Prints each reply's text and keeps
the full replies in <calls.json>.out.txt. A call may carry "source_file": "film.py" (read into args.source)."""
import asyncio, json, os, re, sys, time
sys.stdout.reconfigure(encoding="utf-8")
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

HERE = os.path.dirname(os.path.abspath(__file__))
PY = r"C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\.venv\Scripts\python.exe"
PROJECT = os.environ.get("ROSTRUM_PROJECT", r"C:\Users\Sam\.rostrum\waves\scratch\hem-H11-proof\project")
ITEM = os.environ.get("ROSTRUM_ITEM", "parallax")


def text_of(res):
    return "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")


async def main(path):
    calls = json.load(open(path, encoding="utf-8"))
    log = open(path + ".out.txt", "w", encoding="utf-8")
    params = StdioServerParameters(command=PY, args=["-m", "rostrum2d.mcp", "--project", PROJECT, "--item", ITEM],
                                   env={"PYTHONUTF8": "1", "SYSTEMROOT": r"C:\Windows", "PATH": r"C:\Windows\System32;C:\ffmpeg\bin;" + os.environ["PATH"]})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for c in calls:
                args = dict(c.get("args", {}))
                if "source_file" in c:
                    args["source"] = open(os.path.join(HERE, c["source_file"]), encoding="utf-8").read()
                t0 = time.time()
                res = await s.call_tool(c["tool"], args)
                out = text_of(res)
                job = None
                if out.strip().startswith("{"):
                    try:
                        job = json.loads(out).get("job_id")
                    except Exception:
                        pass
                if job is None and "job_id" in out:
                    m = re.search(r'"?job_id"?\W+([\w\-:.]+)', out)
                    job = m.group(1) if m else None
                while job:
                    res = await s.call_tool("inspect_job", {"job_id": job, "wait_s": 25})
                    out = text_of(res)
                    if '"running"' not in out and "queued" not in out and "status: running" not in out:
                        break
                msg = f"== {c['tool']}{' ERROR' if res.is_error else ''} ({time.time() - t0:.1f} s)\n{out}\n"
                log.write(msg); log.flush()
                print(msg[:int(os.environ.get('SHOW', 3500))], flush=True)

asyncio.run(main(sys.argv[1]))
