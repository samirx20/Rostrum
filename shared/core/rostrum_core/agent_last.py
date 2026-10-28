"""The project an agent last opened through an app's MCP server, per agent session, so a server started again for the same
session reopens that project instead of starting with none.

An agent's run_open_project never touches the person's Open recent list (recent.py); this is a separate, small record:
`~/.rostrum/settings/<app>-agent-last.json` (home() below), {session key: {folder, item}}. The key is the agent's session id
when the agent passes one to its servers (SESSION_VARS: a resumed Claude Code session keeps its id), else the working folder
plus the agent process that started this server (a server restarted inside the same session gets it back). Never the folder
alone: Agent Hub starts every child agent in the same worktree, and a new agent must not be handed another agent's project.

    remember(app, folder, item)         run_open_project calls this (open_folder.py), and start-up for a scratch project
    recall(app, ext)                    start-up (agent_start.py): this folder's row, when its document is still there
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from . import userhome
from .storage import paths, write_atomic

KEEP = 50


def home() -> Path:
    """Where agents' own things live (this record, agent_start's scratch projects): ~/.rostrum even in a run userhome counts
    as scripted (a server started from a worktree gets a temp home, removed at exit, and the agent's work must outlive the
    session). Nothing here is the person's settings or Open recent. ROSTRUM_AGENT_HOME overrides; tests use their scratch home."""
    if os.environ.get("ROSTRUM_AGENT_HOME"):
        return Path(os.environ["ROSTRUM_AGENT_HOME"])
    testing = "pytest" in sys.modules or os.environ.get("PYTEST_CURRENT_TEST")
    return userhome.home() if testing else Path.home() / ".rostrum"


def file(app: str) -> Path:
    return home() / "settings" / f"{app}-agent-last.json"


SESSION_VARS = ("CLAUDE_CODE_SESSION_ID",)         # agents that tell their servers which session they serve


def _here() -> str:
    """This agent session's key (see the module text)."""
    sid = next((os.environ[v] for v in SESSION_VARS if os.environ.get(v)), None)
    if sid:
        return f"session:{sid}"
    return f"{os.path.normcase(str(Path.cwd().resolve()))}|agent:{os.getppid()}"


def _read(app: str) -> dict:
    try:
        data = json.loads(file(app).read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def remember(app: str, folder, item: str) -> None:
    """This working folder's agent now works on `folder` / `item` (newest last; keeps KEEP folders)."""
    try:
        with userhome.locked(file(app)):
            data = _read(app)
            data.pop(_here(), None)
            data[_here()] = {"folder": str(Path(folder).resolve()), "item": item}
            write_atomic(file(app), json.dumps(dict(list(data.items())[-KEEP:]), indent=1, ensure_ascii=False))
    except OSError:
        pass                                     # a record we could not write only loses the reopen convenience


def recall(app: str, ext: str) -> dict | None:
    """{folder, item} this working folder's agent last opened, when its document is still on disk."""
    row = _read(app).get(_here())
    if not row or not paths(row["folder"], row["item"], ext)["doc"].is_file():
        return None
    return {"folder": row["folder"], "item": row["item"]}

