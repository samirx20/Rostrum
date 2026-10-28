"""The exact copy-paste text for each agent: one source for the connect dialog and the guides."""
from __future__ import annotations

import base64
import json
import re
import shlex
from pathlib import Path

import tomlkit

from . import agents, servers

APP_NAMES = {"2d": "Rostrum2D", "sound": "RostrumSound"}


def _quote(arg: str) -> str:
    if re.fullmatch(r"[\w./:\\=+@-]+", arg):
        return arg
    return "'" + arg.replace("'", "''") + "'" if agents.plat() == "win" else shlex.quote(arg)


def _snippet(a: agents.Agent, srv) -> str:
    nested: dict = {srv.name: agents.to_entry(a.shape, srv)}
    for k in reversed(a.key):
        nested = {k: nested}
    return tomlkit.dumps(nested).strip() if a.fmt == "toml" else json.dumps(nested, indent=2, ensure_ascii=False)


def by_hand(agent_id: str, app: str, generic: bool = False) -> dict:
    """`generic`: for the shipped guides (a standard install; the guide puts <you> for this computer's user name)."""
    a, srv = agents.get(agent_id), servers.entry(app, generic=generic)
    entry = agents.to_entry(a.shape, srv)
    command = " ".join(_quote(x) for x in agents.render_argv(a.cli_add, srv, a.shape)) if a.cli_add else None
    link = None
    if a.deeplink:
        b64 = base64.b64encode(json.dumps(agents.to_entry("std", srv), separators=(",", ":")).encode()).decode()
        link = a.deeplink.format(name=srv.name, b64=b64)
    path = agents.user_file(a, generic)
    steps = []
    if command:
        steps.append("Open a terminal and paste the line above, then press Enter.")
    else:
        steps.append(f"Open {path} (make the file if it isn't there).")
        where = " → ".join(f"“{k}”" for k in a.key)
        steps.append(f"Paste the block above inside {where}. If {where} is already there, add only the "
                     f"“{srv.name}” part, and keep your other servers.")
        steps.append("Save the file." if a.fmt != "jsonc" else
                     "Save the file. (It may hold comments: keep them. Rostrum's button refuses such a file rather than lose them.)")
    if link:
        steps.insert(0, "Quickest: open the link above; Cursor asks you to confirm.")
    steps += [a.restart.format(name=a.name), a.check.format(name=a.name)]
    return {"command": command, "file": str(path), "snippet": _snippet(a, srv), "deeplink": link, "steps": steps}


def _remove_how(a: agents.Agent, app: str) -> str:
    srv = servers.entry(app)
    if a.cli_remove:
        return "`" + " ".join(_quote(x) for x in agents.render_argv(a.cli_remove, srv, a.shape)) + "`"
    return f"open {agents.user_file(a, generic=True)} and delete the “{srv.name}” block (keep everything else)."


def guide_markdown(agent_id: str) -> str:
    a = agents.get(agent_id)
    out = [f"# Connect Rostrum to {a.name}", "",
           f"Rostrum2D and RostrumSound each have a small server ({', '.join(f'`{servers.APPS[x][0]}`' for x in servers.APPS)}) "
           f"that lets {a.name} use them. Connecting means telling {a.name} how to start those servers.", "",
           "## The easy way", "",
           f"In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to "
           f"{a.name} and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file "
           f"first, never touches servers it didn't add, and **Remove** takes back only what it added.", "",
           "## By hand", ""]
    for app in servers.APPS:
        h = by_hand(agent_id, app, generic=True)
        out += [f"### {APP_NAMES[app]} (`{servers.APPS[app][0]}`)", ""]
        if h["deeplink"]:
            out += [f"Link: {h['deeplink']}", ""]
        if h["command"]:
            out += ["Terminal:", "", "```", h["command"], "```", ""]
        out += [f"File: `{h['file']}`", "", "```" + ("toml" if a.fmt == "toml" else "json"), h["snippet"], "```", ""]
        out += [f"{i}. {s}" for i, s in enumerate(h["steps"], 1)] + [""]
    out += ["## Check it works", "", a.check.format(name=a.name), "",
            "## Remove it", "", f"Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to {a.name}.", ""]
    out += [f"By hand, for {APP_NAMES[app]}: {_remove_how(a, app)}" + "" for app in servers.APPS]
    out += ["", f"More about {a.name} and MCP servers: {a.docs}", ""]
    text, home = "\n".join(out), Path.home()
    you = str(home.parent / "<you>")
    # the shipped page names no one's computer: this home folder becomes <you>, plain and JSON / TOML escaped
    return text.replace(str(home).replace("\\", "\\\\"), you.replace("\\", "\\\\")).replace(str(home), you)


def write_guides(folder) -> list[Path]:
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    written = []
    for a in agents.AGENTS:
        p = folder / f"{a.id}.md"
        p.write_text(guide_markdown(a.id), encoding="utf-8")
        written.append(p)
    index = ["# Connect Rostrum to your AI agent", "",
             "Pick your agent. Each page shows the easy way inside Rostrum and the by-hand way.",
             "Gemini CLI is not listed: Google stopped it for personal accounts in June 2026. Use Antigravity, its replacement.", ""]
    index += [f"- [{a.name}]({a.id}.md)" for a in agents.AGENTS]
    (folder / "index.md").write_text("\n".join(index) + "\n", encoding="utf-8")
    return written + [folder / "index.md"]
