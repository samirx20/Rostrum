"""Drive the rostrum-2d MCP server over stdio (the only way this proof touches the document).
    python mcp_session.py calls.json      calls = [{"tool": ..., "args": {...}}, ...]
Jobs (look_frame, render_video) are waited for with inspect_job. Prints each reply's text."""
import asyncio, json, sys
sys.stdout.reconfigure(encoding="utf-8")
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

PY = r"C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\.venv\Scripts\python.exe"
PROJECT = r"C:\Users\Sam\.rostrum\waves\scratch\sam-S8-lead\proof\project"


def text_of(res):
    return "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")


async def main(calls):
    params = StdioServerParameters(command=PY, args=["-m", "rostrum2d.mcp", "--project", PROJECT, "--item", "launch"],
                                   env={"PYTHONUTF8": "1", "SYSTEMROOT": r"C:\Windows", "PATH": r"C:\Windows\System32;C:\ffmpeg\bin;" + __import__("os").environ["PATH"]})
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            for c in calls:
                res = await s.call_tool(c["tool"], c.get("args", {}))
                out = text_of(res)
                job = None
                try:
                    job = json.loads(out).get("job_id") if out.strip().startswith("{") else None
                except Exception:
                    pass
                if job is None and "job_id" in out:
                    import re
                    m = re.search(r'"?job_id"?\W+([\w\-:.]+)', out)
                    job = m.group(1) if m else None
                while job:
                    res = await s.call_tool("inspect_job", {"job_id": job, "wait_s": 25})
                    out = text_of(res)
                    if '"running"' not in out and "queued" not in out and "status: running" not in out:
                        break
                print(f"== {c['tool']}{' ERROR' if res.is_error else ''}\n{out[:3000]}\n", flush=True)

asyncio.run(main(json.load(open(sys.argv[1], encoding="utf-8"))))
