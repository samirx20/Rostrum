"""What an app's MCP server opens when it starts, for every app, and the sentence that tells the agent what is open and whose.

An agent session starts safe: with no --project it never opens the person's work. It opens

    asked     --project <folder>: that folder (whoever started the server chose it)
    resumed   the project this agent session last opened (agent_last.py: a resumed session gets its own back)
    scratch   else a fresh scratch project made for the agent, `~/.rostrum/projects/agent-scratch/<app>-<date-time>`,
              with a new empty document; it is remembered, so a resumed session reopens it. Each start removes the
              scratch projects older than 2 days that never got a change (their files exactly as made: `tidy`)

The person's projects open only when the agent asks (run_open_project with a folder, or what "recent" to list them).

    choose(app, ext, project, items, default_item, word)   -> Start(folder, items, whose, word)
    settle(app, start)                                      after the app opened it: the files are on disk, the scratch
                                                            project is remembered, app.opened holds the sentence
"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import agent_last
from .storage import paths

MARK = ".rostrum/agent-scratch.json"          # the files of a scratch project as made: {path: [size, mtime_ns]}
UNTOUCHED_S = 2 * 24 * 3600


@dataclass
class Start:
    folder: str
    items: list
    whose: str                   # "asked" | "resumed" | "scratch"
    word: str = "document"       # what a person calls one document: "document", "song", "scene"

    def sentence(self) -> str:
        what = f'{self.word} "{", ".join(self.items)}"'
        if self.whose == "scratch":
            return (f"Open: a fresh scratch project made for you at {self.folder} ({what}, new), not the person's work. "
                    'To work on one of theirs, call run_open_project with its folder (what "recent" lists them).')
        if self.whose == "resumed":
            return (f"Open: {self.folder} ({what}), your project from earlier in this session (the one you last opened), "
                    'not necessarily the person\'s. Their projects: run_open_project (what "recent").')
        return f"Open: {self.folder} ({what}), the project this server was started with (--project)."


def scratch_root() -> Path:
    return agent_last.home() / "projects" / "agent-scratch"     # kept after the session (not a run's temp home)


def scratch_folder(app: str) -> Path:
    """A new, not yet existing folder for one agent project: `<app>-<date>_<time>` (a number added when taken)."""
    base = scratch_root() / f"{app.removeprefix('rostrum-')}-{datetime.now():%Y-%m-%d_%H%M%S}"
    folder, n = base, 1
    while folder.exists():
        n += 1
        folder = base.with_name(f"{base.name}-{n}")
    return folder


def choose(app: str, ext: str, project: str | None, items: list | None, default_item, word: str = "document") -> Start:
    """What to open at start-up. `default_item(folder, explicit)` is the app's own choice of document in a folder."""
    if project:
        return Start(project, items or [default_item(project, True)], "asked", word)
    tidy()
    mine = agent_last.recall(app, ext)
    if mine:
        return Start(mine["folder"], items or [mine["item"]], "resumed", word)
    folder = scratch_folder(app)
    folder.mkdir(parents=True)
    return Start(str(folder), items or [default_item(str(folder), True)], "scratch", word)


def settle(app, start: Start) -> None:
    """After the app opened `start`: every opened document is on disk (an empty new one too, so a resumed session finds it),
    a scratch project is remembered for this agent session, and `app.opened` says what is open and whose."""
    for item, doc in app.documents.items():
        if not paths(app.folder, item, doc.kind.ext)["doc"].is_file():
            doc.save()
    if start.whose == "scratch" and start.items:
        agent_last.remember(app.name, app.folder, start.items[0])
        (Path(app.folder) / MARK).parent.mkdir(parents=True, exist_ok=True)
        (Path(app.folder) / MARK).write_text(json.dumps(_files(app.folder)), encoding="utf-8")
    app.opened = start.sentence()


def _files(folder) -> dict:
    root = Path(folder)
    return {p.relative_to(root).as_posix(): [p.stat().st_size, p.stat().st_mtime_ns]
            for p in sorted(root.rglob("*")) if p.is_file() and p.relative_to(root).as_posix() != MARK}


def tidy(now: float | None = None) -> None:
    """Remove scratch projects made over UNTOUCHED_S ago whose files are exactly as made (no change, render or look).
    One without its mark, or with any difference at all, is kept."""
    now = time.time() if now is None else now
    for d in scratch_root().iterdir() if scratch_root().is_dir() else ():
        try:
            mark = d / MARK
            if mark.is_file() and now - mark.stat().st_mtime > UNTOUCHED_S and json.loads(mark.read_text(encoding="utf-8")) == _files(d):
                shutil.rmtree(d)
        except (OSError, ValueError):
            pass                                  # a folder we can't read or remove stays; tidying is never worth a failed start
