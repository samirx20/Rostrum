"""The Render page's two lists as plain rows (SPEC §11.3; read by qml/RenderPage.qml through queue.py). No Qt.

The shots list: each shot with its tick for "All shots", its length and when it was last rendered (the newest finished
version of this document whose manifest names the shot; a `.partial` is never one).
The queue: one row per job of the project's jobs queue (rostrum_core.mcp.jobs), in its order: running, waiting, then
the ended ones (done: time taken and folder; failed or cancelled: the reason, in red).
"""
from __future__ import annotations

import calendar
import time

from rostrum_core import project

WORDS = {"queued": "Waiting", "running": "Rendering", "done": "Done", "failed": "Failed", "cancelled": "Render cancelled"}


def _when(made_at: str) -> str:
    """"Today 08:31" or "23 Oct 17:05" (local time) from a manifest's UTC made_at."""
    try:
        t = time.localtime(calendar.timegm(time.strptime(made_at, "%Y-%m-%dT%H:%M:%SZ")))
    except (TypeError, ValueError):
        return ""
    day = "Today" if time.strftime("%Y%m%d", t) == time.strftime("%Y%m%d") else time.strftime("%d %b", t).lstrip("0")
    return f'{day} {time.strftime("%H:%M", t)}'


def last_renders(folder, item_id) -> dict[str, dict]:
    """{shot id: {when, folder} of its newest finished render} for one document of a project ({} outside a project)."""
    out: dict[str, dict] = {}
    if not folder or not item_id:
        return out
    for r in project.renders(folder, item_id):                 # newest first
        shot = r["manifest"].get("source", {}).get("shot")
        if shot and shot not in out:
            out[shot] = {"when": _when(r["manifest"].get("made_at", "")), "folder": r["path"]}
    return out


def seconds_text(s: float) -> str:
    return f"{s:.1f} s" if s < 60 else f"{int(s // 60)} min {int(s % 60):02d} s"


def shot_rows(shots: list[dict], infos: dict[str, dict], shown: str, ticked: set, last: dict[str, dict]) -> list[dict]:
    """`shots`: outline.named rows ({value, label}); `infos`: shot id -> compile.shot_info."""
    rows = []
    for s in shots:
        info = infos.get(s["value"])
        if info is None:
            continue
        frames = info["end"] - info["start"] + 1
        rows.append({"id": s["value"], "label": s["label"], "length": seconds_text(frames / info["fps"]),
                     "last": last.get(s["value"], {}).get("when", ""), "folder": last.get(s["value"], {}).get("folder", ""), "ticked": s["value"] in ticked, "shown": s["value"] == shown})
    return rows


def _left(job) -> str:
    """Time left from the frames done so far ("" until the first frame lands)."""
    run = job.seconds()
    if not job.total or not job.done or run is None:
        return ""
    return seconds_text(run / job.done * (job.total - job.done)) + " left"


def job_row(job, meta: dict, waiting_index: int) -> dict:
    """One queue row. `waiting_index`: its place among the waiting jobs (-1 when it isn't waiting)."""
    st, run = job.status, job.seconds()
    row = {"id": job.id, "status": st, "word": WORDS.get(st, st), "shot": meta["label"], "quality": meta["quality"],
           "size": meta["size"], "done": job.done or 0, "total": job.total or meta["frames"], "left": "", "took": "",
           "folder": meta.get("folder", ""), "picture": meta.get("picture", ""), "reason": "", "place": waiting_index}
    if st == "running":
        row["left"] = _left(job) or ("Starting…" if not job.done else "")
    elif st == "done":
        row["took"] = f"Took {seconds_text(run or 0)}"
    elif st in ("failed", "cancelled"):
        row["reason"] = "nothing was kept as a version" if st == "cancelled" else job.reason
    return row


def queue_rows(jobs, metas: dict[str, dict]) -> list[dict]:
    """The queue in its order (`jobs`: InProcessJobs.listing()), only the jobs this screen added (`metas`)."""
    rows, place = [], 0
    for j in jobs:
        if j.id not in metas:
            continue
        rows.append(job_row(j, metas[j.id], place if j.status == "queued" else -1))
        place += j.status == "queued"
    return rows


def commands(shots: list[dict], rows: list[dict], call) -> list[dict]:
    """The queue's Ctrl K entries: `call(op, args)` is RenderQueue's one door for render.queue.*."""
    out = [{"key": f"render.queue.add:{s['value']}", "label": f"Add {s['label']} to the render queue", "hint": "Render",
            "words": "render queue add", "do": lambda sid=s["value"]: call("render.queue.add", {"shot": sid})} for s in shots]
    return out + [{"key": f"render.queue.cancel:{r['id']}", "label": f"Cancel the render of {r['shot']}", "hint": r["word"],
                   "words": "render queue cancel stop", "do": lambda jid=r["id"]: call("render.queue.cancel", {"job": jid})}
                  for r in rows if r["status"] in ("queued", "running")]
