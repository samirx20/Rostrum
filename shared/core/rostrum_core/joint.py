"""One step across documents (AGENTS.md rule 3; OPERATIONS.md § 6): 2D's "Add a sound here" writes a cue into Sound's
song and a shared marker; Ctrl+Z takes both back as one step. Any app's cross-document operation works the same way.

Every change carries a `step` id (history.Change.step). Changes made while a step is open share its id:

    with joint.step():                       # an app's cross-document operation
        markers.edit(folder, [...], who)     # these changes all get the same step id,
        song.apply([...], who)               # whatever documents they are in

A change made by a listener while another change is being recorded (a cue marker following its layer: links.py)
joins that change's step without anyone opening one: Document._record holds `within(c.step)` while it tells its
listeners. desk.undo / desk.redo then take back or bring back every change of the step, in every document, as one.

The project's step journal (`.rostrum/steps.jsonl`, one line per document a step reached beyond its first) lets an
undo find a document that took part but isn't open on this screen; desk asks the app to open it (`open_item`).
While a step is being taken back or brought back, `replaying()` is true: listeners that keep derived data in place
(links.py) do nothing, since the step's own changes already hold the right values.
"""
from __future__ import annotations

import contextlib
import json
import uuid
from contextvars import ContextVar
from pathlib import Path

from . import filestamps

_current: ContextVar[str | None] = ContextVar("rostrum_step", default=None)
_replay: ContextVar[bool] = ContextVar("rostrum_replay", default=False)
_reached: dict[str, list[str]] = {}          # step id -> documents (item ids) it changed, this process


def new_id() -> str:
    return "st_" + uuid.uuid4().hex[:12]


def current() -> str | None:
    """The open step's id, or None."""
    return _current.get()


@contextlib.contextmanager
def within(step_id: str | None):
    """Changes made inside join `step_id` (an open step is kept: the outer one wins)."""
    if step_id is None or _current.get() is not None:
        yield _current.get()
        return
    tok = _current.set(step_id)
    try:
        yield step_id
    finally:
        _current.reset(tok)


def step():
    """Open one step for an app's operation that changes several documents (nested: joins the outer one)."""
    return within(_current.get() or new_id())


def replaying() -> bool:
    return _replay.get()


@contextlib.contextmanager
def replay():
    tok = _replay.set(True)
    try:
        yield
    finally:
        _replay.reset(tok)


def _journal(folder) -> Path:
    return Path(folder) / ".rostrum" / "steps.jsonl"


def note(doc, step_id: str):
    """Record that `doc` changed in `step_id` (Document._record). A step reaching a second document writes the
    journal lines for both, so an undo elsewhere can find them."""
    if doc.folder is None or doc.item_id is None:
        return
    seen = _reached.setdefault(step_id, [])
    if doc.item_id in seen:
        return
    seen.append(doc.item_id)
    if len(seen) < 2:
        return
    j = _journal(doc.folder)
    j.parent.mkdir(parents=True, exist_ok=True)
    with j.open("a", encoding="utf-8") as f:
        for item in seen[:-1] if len(seen) == 2 else ():
            f.write(json.dumps({"step": step_id, "item": item}) + "\n")
        f.write(json.dumps({"step": step_id, "item": doc.item_id}) + "\n")


def items(folder, step_id: str) -> list[str]:
    """Every document (item id) a step changed, as far as the journal knows (empty: one document only)."""
    j = _journal(folder) if folder is not None else None
    if j is None or filestamps.stamp(j) is None:
        return list(_reached.get(step_id, []))
    out = []
    for line in j.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue                      # a half-written last line: the rest still counts
        if row.get("step") == step_id and row.get("item") not in out:
            out.append(row["item"])
    return out
