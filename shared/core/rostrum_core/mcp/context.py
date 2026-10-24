"""What an app gives the server (`App`) and what a tool receives (`ToolContext`).

`ctx.apply` and `ctx.run_script` are the only ways a tool changes a document: both go through
`Document.apply` / `Document.run_script`, so there is no side door (CONVENTIONS § 5).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Callable

from .. import ids
from ..errors import RostrumError, codes
from ..who import Who
from .guides import Guides
from .jobs import Job, Jobs, outcome
from .reply import Reply

JOB_BUDGET_S = 20          # a tool tries to finish within this, then hands the rest to a job (CONVENTIONS § 7)


@dataclass
class App:
    """One app's side of the server. Tools get it as `ctx.app`."""
    name: str                                               # "rostrum-2d", "rostrum-toy" ...
    documents: dict                                         # open documents by project item id -> Document
    run_source: Callable[[str, str], dict] | None = None    # (python source, file name) -> output tree (the app's script layer)
    instructions: str = ""                                  # the handshake's "start here" for this app
    guides: Guides = field(default_factory=Guides)
    version: str = "0.1.0"
    folder: str | None = None                               # the project folder: inspect_project lists its items
    no_project_hint: str = ""                               # with no folder and nothing open: what to do (inspect_project)
    recent: Callable[[], list] | None = None                # the person's recent projects, shown when none is open
    script_help: str = ""                                   # the script layer in brief: added to run_script's description


class Groups:
    """One group (session) per agent turn. MCP has no turn marker, so a group lasts while calls from the
    same client keep coming within `idle_s`; a quiet gap starts a new one. `group=` always wins. A new group is
    never one already in a saved history (`used()` lists those), so ids stay unique across restarts."""

    def __init__(self, idle_s: float = 20.0, clock=time.monotonic, used=lambda: ()):
        self.idle_s, self._clock, self._used, self._minted = idle_s, clock, used, set()
        self._last: dict[str, tuple[str, float]] = {}

    def current(self, who: Who, asked: str | None = None) -> str:
        now = self._clock()
        last = self._last.get(who.name)
        if asked:
            group = asked
        elif last and now - last[1] <= self.idle_s:
            group = last[0]
        else:
            group = ids.counted(self._minted | set(self._used()), f"{who.name}-run", sep="-")
            self._minted.add(group)
        self._last[who.name] = (group, now)
        return group


@dataclass
class ToolContext:
    app: App
    who: Who
    group: str
    jobs: Jobs
    tool: str                   # the tool being run, for error messages
    tools: object = None        # the server's Tools (for inspect_operations-style lookups)
    notes: list = field(default_factory=list)   # `note`: choices the tool made for the caller, sent as warnings
    seen: list = field(default_factory=list)    # the documents the call was about: their kind's warnings are sent too

    def note(self, text: str):
        """Tell the caller about a choice made for them ("Composition \"film\" (the longest of 2)"); the server
        adds it to the reply's warnings, once, whatever tool made it."""
        if text not in self.notes:
            self.notes.append(text)

    def _saw(self, doc):
        if doc not in self.seen:
            self.seen.append(doc)
        return doc

    def document(self, item: str | None = None):
        """The document a call is about: `item`, or the only open one."""
        docs = self.app.documents
        if item is None:
            if len(docs) == 1:
                return self._saw(next(iter(docs.values())))
            raise RostrumError(codes.BAD_ARGUMENT, self.tool, "argument \"item\"",
                               "is needed: " + ("no document is open" if not docs else "several documents are open"), sorted(docs))
        if item not in docs:
            raise RostrumError.not_found(self.tool, "open document", item, docs, "the open documents")
        return self._saw(docs[item])

    def apply(self, doc, calls, label: str | None = None, group: str | None = None):
        return doc.apply(calls, self.who, label=label, session=group or self.group)

    def run_script(self, doc, name: str, tree: dict, force=False):
        return doc.run_script(name, tree, self.who, force=force, session=self.group)

    def job(self, label: str, fn: Callable[[Job], Reply], key: str | None = None) -> Reply:
        """Always a job (render_* tools): returns at once with the job id."""
        job = self.jobs.submit(label, fn, key)
        return Reply(f"{label}: job {job.id} is {job.status}. Ask with inspect_job.", job.state())

    def long(self, label: str, fn: Callable[[Job], Reply], key: str | None = None, budget_s: float = JOB_BUDGET_S) -> Reply:
        """Finish within `budget_s`, or hand the rest to a job and say so."""
        job = self.jobs.submit(label, fn, key)
        self.jobs.wait(job.id, min(budget_s, 25))
        return outcome(job, self.tool)
