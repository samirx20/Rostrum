"""python -m rostrum_connect found | profiles | status | add | remove | remove-all | entries | hand | guides | table

--everywhere (status, add, remove): also every account folder a launcher made for the agent (profiles.py: Agent Hub keeps
one per Claude account and one per Antigravity account, and each reads only its own file). `profiles` lists them;
remove-all always includes them.

remove-all: takes out every entry Rostrum added, from every agent. The uninstaller runs it first with --this-install:
only the entries that start THIS install's Python (a developer's checkout entries stay)."""
from __future__ import annotations

import argparse
import sys

from . import agents, byhand, connect, profiles, servers
from .configfile import ConnectError


def table_markdown() -> str:
    rows = ["| Agent | Added with | Settings file (Windows) | Table key | Needs a restart? | Docs |",
            "|---|---|---|---|---|---|"]
    for a in agents.AGENTS:
        how = f"`{' '.join(a.cli_add[:3])} …`" if a.cli_add and a.id != "vscode" else \
            f"`code --add-mcp …`, or file edit" if a.cli_add else "file edit"
        if a.deeplink:
            how += " (or link)"
        rows.append(f"| {a.name} | {how} | `{a.files['win']}` | `{'.'.join(a.key)}` ({a.fmt}) | {a.restart} | {a.docs} |")
    return "\n".join(rows)


def _apps(ns) -> list[str]:
    return [ns.app] if getattr(ns, "app", None) else list(servers.APPS)


def _strings(v) -> list[str]:
    if isinstance(v, dict):
        return [s for x in v.values() for s in _strings(x)]
    if isinstance(v, list):
        return [s for x in v for s in _strings(x)]
    return [v] if isinstance(v, str) else []


def _starts_here(entry: dict, app: str) -> bool:
    """Does this agent entry start the Python that `servers.entry` picks here (this install's own)?"""
    here = servers.entry(app).command.lower()
    return any(s.lower() == here for s in _strings(entry))


def _targets(agent_id: str, everywhere: bool) -> list[tuple[str, object]]:
    """(agent id, settings file or None for its usual one): the usual file, plus every account folder when `everywhere`."""
    usual = agents.user_file(agents.get(agent_id)).resolve()       # inside an account's session the usual file IS that one
    return [(agent_id, None)] + ([(p.agent.id, p.file) for p in profiles.found(agent_id)
                                  if p.file.resolve() != usual] if everywhere else [])


def run(ns) -> int:
    ask = (lambda q: True) if getattr(ns, "yes", False) else (lambda q: input(q + " [y/N] ").strip().lower() == "y")
    if ns.cmd == "found":
        for f in connect.agents_found():
            print(f"{'yes' if f.installed else 'no ':3} {f.agent.id:15} {f.how}")
    elif ns.cmd == "profiles":
        for p in profiles.found():
            print(f"{p.agent.id:15} {p.label:28} {p.file}")
    elif ns.cmd == "status":
        for a in [agents.get(ns.agent)] if ns.agent else agents.AGENTS:
            for aid, file in _targets(a.id, ns.everywhere):
                for app in _apps(ns):
                    s = connect.status(aid, app, file)
                    who = "ours" if s.ours else "someone else's" if s.foreign else "not added"
                    print(f"{a.id:15} {app:6} {who:14} {s.file}")
    elif ns.cmd == "add":
        for aid, file in _targets(ns.agent, ns.everywhere):
            for app in _apps(ns):
                r = connect.add(aid, app, ask=ask, file=file)
                print(r.summary + (f"\n  backup: {r.backup}" if r.backup else ""))
                if not r.ok:
                    return 1
    elif ns.cmd == "remove":
        for aid, file in _targets(ns.agent, ns.everywhere):
            for app in _apps(ns):
                print(connect.remove(aid, app, file).summary)
    elif ns.cmd == "remove-all":
        failed = 0
        for aid, file in [t for a in agents.AGENTS for t in _targets(a.id, True)]:
            for app in servers.APPS:
                try:
                    st = connect.status(aid, app, file)
                    if st.ours and not (ns.this_install and not _starts_here(st.entry, app)):
                        print(connect.remove(aid, app, file).summary)
                except ConnectError as e:      # one agent's broken file must not stop the rest; still fails at the end
                    print(f"Error: {aid} ({file or 'its usual file'}), {app}: {e}", file=sys.stderr)
                    failed = 1
        return failed
    elif ns.cmd == "entries":
        for name, ours in connect.entries(ns.agent).items():
            print(f"{name}{'  (added by Rostrum)' if ours else ''}")
    elif ns.cmd == "hand":
        for app in _apps(ns):
            h = byhand.by_hand(ns.agent, app)
            for label in ("command", "deeplink"):
                if h[label]:
                    print(f"{label}: {h[label]}")
            print(f"file: {h['file']}\n{h['snippet']}")
            print("\n".join(f"{i}. {s}" for i, s in enumerate(h["steps"], 1)))
    elif ns.cmd == "guides":
        for p in byhand.write_guides(ns.out):
            print(p)
    elif ns.cmd == "table":
        print(table_markdown())
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="rostrum_connect", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("found", "profiles", "status", "add", "remove", "remove-all", "entries", "hand", "guides", "table"):
        p = sub.add_parser(name)
        if name in ("status", "add", "remove", "entries", "hand"):
            p.add_argument("--agent", required=name != "status", choices=list(agents.BY_ID))
        if name in ("status", "add", "remove", "hand"):
            p.add_argument("--app", choices=list(servers.APPS), required=name == "hand")
        if name in ("status", "add", "remove"):
            p.add_argument("--everywhere", action="store_true",
                           help="Also every account folder a launcher (Agent Hub) made for the agent.")
        if name in ("add", "remove-all"):
            p.add_argument("--yes", action="store_true", help="Don't ask; answer yes to every question.")
        if name == "remove-all":
            p.add_argument("--this-install", action="store_true",
                           help="Only entries that start this install's Python (what the uninstaller removes).")
        if name == "guides":
            p.add_argument("--out", required=True)
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        return run(ap.parse_args(argv))
    except ConnectError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
