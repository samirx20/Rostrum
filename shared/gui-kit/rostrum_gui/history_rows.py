"""The History sheet's rows, as plain data (no Qt): who changed what and when, newest first (INTERACTION.md 1.9, 1.18).

Built on `rostrum_core.desk.changes(docs)`, the one "who changed what" list across the document and its joined
partners (the shared markers). Each original change by a person or a script is one "step" row. An agent's
changes in one session, one after another, fold into ONE "run" row (its steps inside, newest first). Undo and redo
steps are not rows of their own: the row they acted on says `undone` while it is taken back.

`who_name` is the one place a Who becomes words ("You", "Claude", "logo.py"); the agent chip uses it too.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import PurePath

from rostrum_core import desk

SHOWS = ("everyone", "you", "agents", "scripts")
_AGENTS = (("claude", "Claude"), ("codex", "Codex"), ("gemini", "Gemini"), ("cursor", "Cursor"))


def who_name(who, me=None) -> str:
    """A Who in words: "You" for this window's person; an agent by its app ("claude-code" -> "Claude");
    a script by its file name; a change made outside Rostrum as "Outside Rostrum"."""
    if me is not None and who == me:
        return "You"
    if who.kind == "agent":
        low = who.name.lower()
        hit = next((word for key, word in _AGENTS if low.startswith(key)), None)
        return hit or (who.name[:1].upper() + who.name[1:])
    if who.kind == "script":
        return PurePath(who.name.replace("\\", "/")).name or who.name
    if who.kind == "outside":
        return "Outside Rostrum"
    return who.name[:1].upper() + who.name[1:]


def clock(change) -> str:
    """The change's local time of day, "14:02" (old histories without a clock time: their saved UTC stamp)."""
    t = change.t
    if not t and change.when:
        try:
            t = datetime.strptime(change.when, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).timestamp()
        except ValueError:
            return ""
    return time.strftime("%H:%M", time.localtime(t)) if t else ""


def _folds(c) -> bool:
    """An agent's change (or a script it ran) that belongs to a run: it carries the run's session."""
    return c.session is not None and c.who.kind in ("agent", "script")


def _step(i, doc, c, me) -> dict:
    return {"kind": "step", "who": who_name(c.who, me), "whoKind": c.who.kind, "label": c.label, "when": clock(c),
            "seq": c.seq, "doc": i, "item": doc.item_id or "", "session": c.session or "", "count": 1,
            "undone": not doc.history.done[c.seq], "steps": []}


def _run(steps: list[dict]) -> dict:
    """One row for an agent's run; `steps` oldest first. It is undone when every step in it is."""
    newest = steps[-1]
    n = len(steps)
    return {**newest, "kind": "run", "count": n, "label": f"{n} change{'s' if n != 1 else ''}: {newest['label']}",
            "undone": all(s["undone"] for s in steps), "steps": steps[::-1]}


def _keep(row, me_kind_you: bool, show: str) -> bool:
    if show == "everyone":
        return True
    if show == "you":
        return me_kind_you
    return row["whoKind"] == {"agents": "agent", "scripts": "script"}[show]


def rows(docs, me, show="everyone") -> list[dict]:
    """Every original change of `docs` (the document first, then its partners) as History rows, newest first.
    `show`: "everyone" | "you" | "agents" | "scripts". A row's `doc` is the index of its document in `docs`."""
    if show not in SHOWS:
        raise ValueError(f"history rows: show must be one of {SHOWS}, not {show!r}")
    index = {id(d): i for i, d in enumerate(docs)}
    out, run, run_key = [], [], None          # out: (row, made by me); run: the steps of the open agent run
    for doc, c in desk.changes(docs):
        if not c.original:
            continue
        key = (c.who, c.session) if _folds(c) else None
        if run and key != run_key:
            out.append((_run(run), False))
            run = []
        if key is not None:
            run, run_key = run + [_step(index[id(doc)], doc, c, me)], key
        else:
            out.append((_step(index[id(doc)], doc, c, me), c.who == me))
    if run:
        out.append((_run(run), False))
    return [r for r, mine in reversed(out) if _keep(r, mine, show)]


def versions(doc) -> list[dict]:
    """The document's named versions, newest first: {name, at (its step), when ("14:02"; "" for the start)}."""
    named = sorted(doc.versions().items(), key=lambda kv: -kv[1])
    return [{"name": n, "at": s, "when": clock(doc.history.get(s)) if s > 0 else ""} for n, s in named]
