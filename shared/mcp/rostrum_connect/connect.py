"""Connect Rostrum's MCP servers to a coding agent. The GUI dialog and the CLI both call only this."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from . import agents, before, servers
from .configfile import ConnectError, backup, read, table, write


@dataclass
class Found:
    agent: agents.Agent
    installed: bool
    how: str


@dataclass
class Status:
    agent: agents.Agent
    app: str
    installed: bool
    file: Path
    ours: bool
    foreign: bool
    entry: dict | None


@dataclass
class Result:
    ok: bool
    summary: str
    file: Path
    backup: Path | None
    used_cli: bool


def _cli(a: agents.Agent) -> str | None:
    if os.environ.get("ROSTRUM_CONNECT_NO_CLI") == "1" or not a.button_cli:
        return None
    return next((p for c in a.clis if (p := shutil.which(c))), None)


def _found(a: agents.Agent) -> Found:
    for c in a.clis:
        if p := shutil.which(c):
            return Found(a, True, f"cli {p}")
    for d in a.detect_paths:
        if (p := agents.expand(d)).exists():
            return Found(a, True, f"config folder {p}")
    return Found(a, False, "not found")


def agents_found() -> list[Found]:
    return sorted((_found(a) for a in agents.AGENTS), key=lambda f: not f.installed)


def _ours(entry, a: agents.Agent | None = None, name: str = "") -> bool:
    if agents.entry_env(entry).get("ROSTRUM_ADDED_BY") == servers.MARKER["ROSTRUM_ADDED_BY"]:
        return True
    if not (a and a.know_by_module and isinstance(entry, dict)):     # a hand-made entry that starts our own server
        return False
    app = next((v for v in servers.APPS.values() if v[0] == name), None)
    args = entry.get("args") or []
    return bool(app) and "serverUrl" not in entry and list(args[:2]) == ["-m", app[1]]


def _entries(a: agents.Agent) -> dict:
    doc = read(agents.user_file(a), a.fmt)
    return dict(table(doc.data, a.key, fmt=a.fmt) or {})


def entries(agent_id: str) -> dict:
    """Every MCP server name in the agent's user file → True when Rostrum added it."""
    a = agents.get(agent_id)
    return {n: _ours(e, a, n) for n, e in _entries(a).items()}


def status(agent_id: str, app: str) -> Status:
    a, name = agents.get(agent_id), servers.entry(app).name
    e = _entries(a).get(name)
    ours = e is not None and _ours(e, a, name)
    return Status(a, app, _found(a).installed, agents.user_file(a), ours,
                  e is not None and not ours, None if e is None else _plain(e))


def _plain(e):
    return json.loads(json.dumps(e, default=lambda o: o.unwrap() if hasattr(o, "unwrap") else str(o)))


def _run(argv: list[str]) -> None:
    try:
        p = subprocess.run(argv, capture_output=True, text=True, timeout=60, encoding="utf-8", errors="replace")
    except (OSError, subprocess.SubprocessError) as e:
        raise ConnectError(f"Couldn't run {argv[0]} ({e}).")
    if p.returncode != 0:
        raise ConnectError(f"{argv[0]} said no (exit {p.returncode}): {(p.stdout + p.stderr).strip() or 'no message'}")


def _edit(a: agents.Agent, mutate, hand: str = "") -> None:
    path = agents.user_file(a)
    doc = read(path, a.fmt)
    mutate(doc)
    write(path, a.fmt, doc, hand)


def _check_listed(a: agents.Agent, app: str, expect: bool, via: str) -> None:
    st = status(a.id, app)
    if st.ours != expect:
        raise ConnectError(f"I tried {via} but {st.file} doesn't show {servers.entry(app).name} "
                           f"{'added' if expect else 'removed'} afterwards. Nothing more was changed; "
                           f"use “Show me how to do it by hand”.")


def add(agent_id: str, app: str, ask=None, project: str | None = None) -> Result:
    from .byhand import by_hand
    a, srv = agents.get(agent_id), servers.entry(app, project)
    st = status(agent_id, app)
    if st.foreign:
        raise ConnectError(f"{st.file} already has a server called {srv.name} that Rostrum didn't add. "
                           f"I won't touch it. Remove or rename it first, then try again.")
    if ask and not st.installed and not ask(f"{a.name} doesn't look installed here. Add Rostrum to its settings anyway?"):
        return Result(False, f"Left {a.name} alone.", st.file, None, False)
    if ask and not st.file.exists() and not ask(f"{st.file} doesn't exist yet. Create it?"):
        return Result(False, f"Left {a.name} alone.", st.file, None, False)
    saved, cli = backup(st.file, a.id), _cli(a)
    before.note(st.file, a.fmt, a.key)
    hand = by_hand(a.id, app)["snippet"]
    if cli and a.cli_add:
        if st.ours and a.cli_remove:
            _run([cli, *agents.render_argv(a.cli_remove, srv, a.shape)[1:]])
        elif st.ours:
            _edit(a, lambda d: table(d.data, a.key, fmt=a.fmt).pop(srv.name, None), hand)
        _run([cli, *agents.render_argv(a.cli_add, srv, a.shape)[1:]])
    else:
        entry = agents.to_entry(a.shape, srv)
        _edit(a, lambda d: table(d.data, a.key, True, a.fmt).__setitem__(srv.name, entry), hand)
    _check_listed(a, app, True, f"to add it with {'its command' if cli and a.cli_add else 'a file edit'}")
    return Result(True, f"{srv.name} is now in {a.name}'s settings ({st.file}). {a.restart.format(name=a.name)}",
                  st.file, saved, bool(cli and a.cli_add))


def remove(agent_id: str, app: str) -> Result:
    a, srv = agents.get(agent_id), servers.entry(app)
    st = status(agent_id, app)
    if st.foreign:
        raise ConnectError(f"{srv.name} in {st.file} wasn't added by Rostrum, so I won't remove it.")
    if not st.ours:
        return Result(True, f"{srv.name} wasn't in {a.name}'s settings. Nothing to remove.", st.file, None, False)
    saved, cli = backup(st.file, a.id), _cli(a)
    if cli and a.cli_remove:
        _run([cli, *agents.render_argv(a.cli_remove, srv, a.shape)[1:]])
    else:
        _edit(a, lambda d: table(d.data, a.key).pop(srv.name, None))
    before.tidy(st.file, a.fmt, a.key, _drop_table, lambda e: _ours(e, a, srv.name))   # the last of ours gone: the file as it was before us
    _check_listed(a, app, False, "to remove it")
    return Result(True, f"{srv.name} is removed from {a.name}'s settings ({st.file}). {a.restart.format(name=a.name)}",
                  st.file, saved, bool(cli and a.cli_remove))


def _drop_table(data, key: tuple) -> None:
    parents = [data]
    for k in key[:-1]:
        parents.append(parents[-1][k])
    del parents[-1][key[-1]]
