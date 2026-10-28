"""Other settings folders an agent has on this computer. A launcher that runs an agent once per account gives every account
its own folder, and that agent reads ITS folder's settings file, never the person's usual one (Agent Hub: one Claude config
folder per Claude account, one GEMINI_HOME per Antigravity account, MCP servers deliberately not shared). Rostrum's
servers reach those agents only when they are added to each folder's file too.

DATA: one `Launcher` per launcher; `find` reads that launcher's own settings and names (agent id, account, folder).
The file inside a folder is the agent's `files_env[1]` (agents.py), the same name the agent itself looks for.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import agents


@dataclass(frozen=True)
class Profile:
    agent: agents.Agent
    label: str          # "<launcher>: <account>", for people
    file: Path          # the settings file the agent reads in that folder


@dataclass(frozen=True)
class Launcher:
    id: str
    name: str
    settings: str                                       # the launcher's own settings file (agents.expand paths)
    find: Callable[[dict, Path], list[tuple[str, str, Path]]]


def _agent_hub(data: dict, settings: Path) -> list[tuple[str, str, Path]]:
    """Agent Hub: providerInstances → Claude `config.homePath` (CLAUDE_CONFIG_DIR) or Antigravity's per-account GEMINI_HOME,
    `<state>/providers/antigravity/<sha256 of the instance id>` (its antigravityAuthSupport.ts)."""
    out = []
    for iid, inst in (data.get("providerInstances") or {}).items():
        if not isinstance(inst, dict) or inst.get("deleted") or inst.get("enabled") is False:
            continue
        label = inst.get("displayName") or iid
        if inst.get("driver") == "claudeAgent" and (home := (inst.get("config") or {}).get("homePath")):
            out.append(("claude-code", label, agents.expand(home)))
        elif inst.get("driver") == "antigravity":
            key = hashlib.sha256(iid.encode()).hexdigest()
            out.append(("antigravity", label, settings.parent / "providers" / "antigravity" / key))
    return out


LAUNCHERS = (
    Launcher("agent-hub", "Agent Hub", "~/.t3/userdata/settings.json", _agent_hub),
)


def found(agent_id: str | None = None) -> list[Profile]:
    """Every account folder a launcher made for an agent (only folders that exist: an account never started has none)."""
    out: list[Profile] = []
    for ln in LAUNCHERS:
        path = agents.expand(ln.settings)
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for aid, label, folder in ln.find(data, path):
            a = agents.BY_ID.get(aid)
            if a is None or not a.files_env or (agent_id and aid != agent_id) or not folder.is_dir():
                continue
            out.append(Profile(a, f"{ln.name}: {label}", folder / a.files_env[1]))
    return out
