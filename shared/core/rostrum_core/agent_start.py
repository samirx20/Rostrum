"""What an app's MCP server opens when it starts, for every app, and the sentence that tells the agent what is open and whose.

An agent session starts safe: with no --project it never opens the person's work. It opens

    asked     --project <folder>: that folder (whoever started the server chose it)
    joined    the folder this agent session's other app works on (agent_last.film): 2D and Sound started for one film
              share one project, so the song made in Sound is the one under 2D's export; the newest folder any of the
              session's apps opened wins (the agent's or person's run_open_project), the app's own document in it
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
import os
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
    whose: str                   # "asked" | "joined" | "resumed" | "scratch"
    word: str = "document"       # what a person calls one document: "document", "song", "scene"

    def sentence(self) -> str:
        what = f'{self.word} "{", ".join(self.items)}"'
        if self.whose == "scratch":
            return (f"Open: a fresh scratch project made for you at {self.folder} ({what}, new), not the person's work. "
                    'To work on one of theirs, call run_open_project with its folder (what "recent" lists them).')
        if self.whose == "joined":
            return (f"Open: {self.folder} ({what}), the project your other Rostrum app works on in this session, so "
                    "music, markers and picture share one project. Another folder: run_open_project.")
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
    with agent_last.film_lock():                  # two servers starting at once: the second joins the first's folder
        film = agent_last.film()
        if film and not (mine and _same(mine["folder"], film["folder"])):
            return Start(film["folder"], items or [default_item(film["folder"], True)], "joined", word)
        if mine:
            return Start(mine["folder"], items or [mine["item"]], "resumed", word)
        folder = scratch_folder(app)
        folder.mkdir(parents=True)
        agent_last.set_film(app, folder)
    return Start(str(folder), items or [default_item(str(folder), True)], "scratch", word)


def _same(a, b) -> bool:
    return os.path.normcase(str(Path(a).resolve())) == os.path.normcase(str(Path(b).resolve()))


def settle(app, start: Start) -> None:
    """After the app opened `start`: every opened document is on disk (an empty new one too, so a resumed session finds it),
    the project is remembered for this agent session (and its other apps), and `app.opened` says what is open and whose."""
    for item, doc in app.documents.items():
        if not paths(app.folder, item, doc.kind.ext)["doc"].is_file():
            doc.save()
    if start.whose in ("scratch", "joined", "asked") and start.items:
        agent_last.remember(app.name, app.folder, start.items[0])   # the film record too: the other app joins this folder
    if start.whose in ("scratch", "joined") and _same(Path(app.folder).parent, scratch_root()):
        (Path(app.folder) / MARK).parent.mkdir(parents=True, exist_ok=True)       # as made, the joining app's file too
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
