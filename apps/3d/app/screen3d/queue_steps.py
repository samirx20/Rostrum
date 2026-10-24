"""Scripted steps for the Render page's queue (steps.py hands `queue …` here). Each goes through RenderQueue.call, the
same door the page's buttons use:

    queue add <shot id> [first] | queue move <row> <index> | queue cancel <row> | queue show <row>   (row: 0-based, as listed)
    queue wait-frames <n> (until the running render has n frames) | queue wait-idle (until nothing waits or runs)
    queue report (prints the rows, the engine PIDs and the render folders: the walk's evidence)
    queue demo (plants fixed rows, never a render: the layout check's pictures)
"""
from __future__ import annotations

import time

from PySide6.QtCore import QCoreApplication
from PySide6.QtTest import QTest
from rostrum_core.mcp.jobs import Job

WAIT_S = 600


def _row(q, n: str) -> dict:
    q.refresh()
    rows = q.rows
    if not rows or int(n) >= len(rows):
        raise RuntimeError(f"queue: no row {n} (there are {len(rows)})")
    return rows[int(n)]


def _until(q, test, what):
    t0 = time.monotonic()
    while not test():
        if time.monotonic() - t0 > WAIT_S:
            raise RuntimeError(f"queue: {what} did not happen in {WAIT_S} s")
        QTest.qWait(100)
        QCoreApplication.processEvents()
    q.refresh()


def _report(q, bridge):
    from pathlib import Path
    q.refresh()
    for r in q.rows:
        m = q._meta[r["id"]]
        proc = m.get("ended_proc")
        ended = f'ended pid {m["ended_pid"]} (exit {proc.poll() if proc else "-"})' if m.get("ended_pid") else ""
        print(f'queue row: {r["shot"]} {r["status"]} frames {r["done"]}/{r["total"]} {r["took"]} {r["reason"]} '
              f'engine pid {m.get("pid")} {ended} folder {r["folder"]}', flush=True)
    base = Path(bridge.doc.folder or ".") / "renders" / (bridge.doc.item_id or "-")
    for d in sorted(base.iterdir()) if base.is_dir() else ():
        print(f"render folder: {d.name} ({len(list(d.iterdir()))} files)", flush=True)


def demo(q, picture: str):
    """Fixed rows for pictures: Hero 01 running (5 of 12), Close 02 waiting, Hero 01 cancelled, Close 02 done."""
    now = time.monotonic()
    plan = [("hero", "Hero 01", "running", 5, 40.0, None), ("close", "Close 02", "queued", 0, None, None),
            ("hero", "Hero 01", "cancelled", 3, 90.0, 70.0), ("close", "Close 02", "done", 12, 200.0, 152.0)]
    for shot, label, status, done, start, end in plan:
        j = Job(f"render {shot}", None)
        j.status, j.done, j.total = status, done or None, 12
        j.started, j.ended = (now - start if start else None), (now - end if end else None)
        j.reason = "cancelled" if status == "cancelled" else ""
        if status in ("done", "cancelled"):
            j.finished.set()
        q.jobs._jobs[j.id] = j
        q.jobs._order.append(j)
        folder = f"renders/{label.replace(' ', '_').lower()}/v002" if status == "done" else ""
        q._meta[j.id] = {"label": label, "quality": "Draft", "size": "960 × 540", "frames": 12, "pid": None,
                         "folder": folder, "picture": picture if status == "done" else ""}
    q.refresh()
    q._poll.stop()                    # fixed rows: nothing moves


def do(bridge, rest: list[str]):
    q, word = bridge.queue, rest[0]
    if word == "add":
        q.call("render.queue.add", {"shot": rest[1], "first": "first" in rest[2:]})
    elif word == "move":
        q.call("render.queue.move", {"job": _row(q, rest[1])["id"], "index": int(rest[2])})
    elif word == "cancel":
        r = _row(q, rest[1])
        q.call("render.queue.cancel", {"job": r["id"]})
        print(f'queue cancel: {r["shot"]} was {r["status"]}; engine pid {q._meta[r["id"]].get("pid")}', flush=True)
    elif word == "show":
        q.show(_row(q, rest[1])["id"])
    elif word == "wait-frames":
        _until(q, lambda: any(j.status == "running" and (j.done or 0) >= int(rest[1]) for j in q.jobs.listing()), f"{rest[1]} frames")
    elif word == "wait-idle":
        _until(q, lambda: not any(j.status in ("queued", "running") for j in q.jobs.listing()), "the queue's end")
    elif word == "report":
        _report(q, bridge)
    elif word == "demo":
        from .steps import recorded_estimate
        demo(q, recorded_estimate()["picture"])
    else:
        raise ValueError(f"unknown queue step {word!r}")
