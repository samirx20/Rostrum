"""python -m rostrum_connect found | status | add | remove | remove-all | entries | hand | guides | table

remove-all: takes out every entry Rostrum added, from every agent (the uninstaller runs it first)."""
from __future__ import annotations

import argparse
import sys

from . import agents, byhand, connect, servers
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


def run(ns) -> int:
    ask = (lambda q: True) if getattr(ns, "yes", False) else (lambda q: input(q + " [y/N] ").strip().lower() == "y")
    if ns.cmd == "found":
        for f in connect.agents_found():
            print(f"{'yes' if f.installed else 'no ':3} {f.agent.id:15} {f.how}")
    elif ns.cmd == "status":
        for a in [agents.get(ns.agent)] if ns.agent else agents.AGENTS:
            for app in _apps(ns):
                s = connect.status(a.id, app)
                who = "ours" if s.ours else "someone else's" if s.foreign else "not added"
                print(f"{a.id:15} {app:6} {who:14} {s.file}")
    elif ns.cmd == "add":
        for app in _apps(ns):
            r = connect.add(ns.agent, app, ask=ask)
            print(r.summary + (f"\n  backup: {r.backup}" if r.backup else ""))
            if not r.ok:
                return 1
    elif ns.cmd == "remove":
        for app in _apps(ns):
            print(connect.remove(ns.agent, app).summary)
    elif ns.cmd == "remove-all":
        failed = 0
        for a in agents.AGENTS:
            for app in servers.APPS:
                try:
                    if connect.status(a.id, app).ours:
                        print(connect.remove(a.id, app).summary)
                except ConnectError as e:      # one agent's broken file must not stop the rest; still fails at the end
                    print(f"Error: {a.name}, {app}: {e}", file=sys.stderr)
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
    for name in ("found", "status", "add", "remove", "remove-all", "entries", "hand", "guides", "table"):
        p = sub.add_parser(name)
        if name in ("status", "add", "remove", "entries", "hand"):
            p.add_argument("--agent", required=name != "status", choices=list(agents.BY_ID))
        if name in ("status", "add", "remove", "hand"):
            p.add_argument("--app", choices=list(servers.APPS), required=name == "hand")
        if name in ("add", "remove-all"):
            p.add_argument("--yes", action="store_true", help="Don't ask; answer yes to every question.")
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
