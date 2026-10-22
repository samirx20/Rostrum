"""The table of coding agents Rostrum can connect to. It is DATA: one `Agent` per agent, no per-agent code.

Everything else (connect, byhand, the GUI dialog, shared/mcp/AGENTS.md) is built from this list.
Paths use `~`, `%APPDATA%` and `%LOCALAPPDATA%`; `expand` turns them into real paths on any system.
Command templates (`cli_add`, `cli_remove`, `cli_list`) are argv lists with these tokens:
  {name}          the server's name              {cmd}           the command followed by its arguments
  {env:-e}        one "-e K=V" pair per variable (any flag name after "env:")
  {json}          {"name", "command", "args", "env"} as one JSON text
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Agent:
    id: str
    name: str
    docs: str                       # the agent's own page about MCP servers
    clis: tuple                     # command names that show the agent is installed
    files: dict                     # user-level config file per system: "win" / "mac" / "linux"
    fmt: str                        # "json" | "jsonc" | "toml"
    key: tuple                      # path to the servers table inside the file
    shape: str                      # "std" | "claude-code" | "vscode" | "opencode" | "zed"
    detect_paths: tuple = ()        # folders whose presence means the app is installed
    files_env: tuple | None = None  # (environment variable, file name): that folder replaces the default
    candidates: tuple = ()          # other places the file can live; the first that exists wins over `files`
    project_file: str | None = None
    cli_add: tuple | None = None
    cli_remove: tuple | None = None
    cli_list: tuple | None = None
    deeplink: str | None = None
    button_cli: bool = True        # False: the agent's CLI rewrites the person's whole file, so Add / Remove edit it ourselves
    restart: str = "Close and reopen {name}."
    check: str = "Ask {name} to list its tools; rostrum-2d and rostrum-sound should be there."


_ALL = {"win": "", "mac": "", "linux": ""}


def _same(path: str) -> dict:
    return {k: path for k in _ALL}


AGENTS = (
    Agent("claude-code", "Claude Code", "https://code.claude.com/docs/en/mcp", ("claude",),
          _same("~/.claude.json"), "json", ("mcpServers",), "claude-code",
          detect_paths=("~/.claude",), files_env=("CLAUDE_CONFIG_DIR", ".claude.json"), project_file=".mcp.json",
          cli_add=("claude", "mcp", "add", "--scope", "user", "{env:-e}", "--transport", "stdio", "{name}", "--", "{cmd}"),
          cli_remove=("claude", "mcp", "remove", "--scope", "user", "{name}"),
          cli_list=("claude", "mcp", "list"),
          restart="Start a new Claude Code session (servers load when it starts).",
          check="In Claude Code type /mcp (or run `claude mcp list`); rostrum-2d and rostrum-sound should be listed as connected."),
    Agent("claude-desktop", "Claude Desktop", "https://modelcontextprotocol.io/docs/develop/connect-local-servers", (),
          {"win": "%APPDATA%/Claude/claude_desktop_config.json",
           "mac": "~/Library/Application Support/Claude/claude_desktop_config.json",
           "linux": "~/.config/Claude/claude_desktop_config.json"},
          "json", ("mcpServers",), "std", detect_paths=("%APPDATA%/Claude", "~/Library/Application Support/Claude"),
          candidates=("%LOCALAPPDATA%/Packages/Claude_pzs8sxrjxfjjc/LocalCache/Roaming/Claude/claude_desktop_config.json",),  # Store install
          restart="Quit Claude Desktop completely (also from the tray) and open it again.",
          check="Click the “+” (Add files, connectors, and more) at the bottom-left of the message box, then Connectors; "
                "rostrum-2d and rostrum-sound should be listed. (The Microsoft Store version reads a different file than "
                "Settings → Developer → Edit Config opens; Rostrum uses the one the app reads.)"),
    Agent("codex", "Codex", "https://developers.openai.com/codex/mcp", ("codex",),
          _same("~/.codex/config.toml"), "toml", ("mcp_servers",), "std",
          detect_paths=("~/.codex",), files_env=("CODEX_HOME", "config.toml"),
          cli_add=("codex", "mcp", "add", "{name}", "{env:--env}", "--", "{cmd}"),
          cli_remove=("codex", "mcp", "remove", "{name}"), cli_list=("codex", "mcp", "list"),
          button_cli=False,        # `codex mcp add/remove` re-sorts and re-types every table (H26 proof); tomlkit keeps it
          restart="Start a new Codex session.", check="Run `codex mcp list`; both servers should be listed."),
    Agent("cursor", "Cursor", "https://cursor.com/docs/context/mcp", ("cursor",),
          _same("~/.cursor/mcp.json"), "json", ("mcpServers",), "std",
          detect_paths=("~/.cursor", "%LOCALAPPDATA%/Programs/cursor", "/Applications/Cursor.app"),
          project_file=".cursor/mcp.json",
          deeplink="cursor://anysphere.cursor-deeplink/mcp/install?name={name}&config={b64}",
          restart="Quit Cursor and open it again.",
          check="Look under Customize in Cursor's sidebar; both servers should be listed with their switch on."),
    Agent("vscode", "VS Code", "https://code.visualstudio.com/docs/copilot/customization/mcp-servers", ("code",),
          {"win": "%APPDATA%/Code/User/mcp.json", "mac": "~/Library/Application Support/Code/User/mcp.json",
           "linux": "~/.config/Code/User/mcp.json"},
          "jsonc", ("servers",), "vscode", detect_paths=("%APPDATA%/Code", "~/Library/Application Support/Code"),
          cli_add=("code", "--add-mcp", "{json}"),
          button_cli=False,        # `code --add-mcp` also writes its own "inputs": [] (H26 proof); a file edit leaves only ours
          restart="Nothing to restart: run the command “MCP: List Servers”, pick the server and choose Start.",
          check="Run the command “MCP: List Servers”; both should be listed."),
    Agent("windsurf", "Windsurf", "https://docs.windsurf.com/windsurf/cascade/mcp", ("windsurf",),
          _same("~/.codeium/windsurf/mcp_config.json"), "json", ("mcpServers",), "std",
          detect_paths=("~/.codeium/windsurf",), candidates=("%APPDATA%/devin/mcp_config.json", "~/.config/devin/mcp_config.json"),
          restart="In Cascade press the refresh button next to the plugins, or restart Windsurf.",
          check="Open the “…” menu in the Cascade panel → MCPs; both servers should be listed. "
                "(Unsure which file your Windsurf reads? Use its “Open MCP config file” button.)"),
    Agent("gemini", "Gemini CLI", "https://geminicli.com/docs/tools/mcp-server/", ("gemini",),
          _same("~/.gemini/settings.json"), "json", ("mcpServers",), "std", detect_paths=("~/.gemini",),
          cli_add=("gemini", "mcp", "add", "{env:-e}", "-s", "user", "{name}", "{cmd}"),
          cli_remove=("gemini", "mcp", "remove", "-s", "user", "{name}"), cli_list=("gemini", "mcp", "list"),
          restart="Start a new Gemini CLI session.", check="In Gemini CLI type /mcp (or run `gemini mcp list`); both should be listed. "
                "Gemini switches every such server off in a folder you haven't trusted (it then says Disabled): "
                "start Gemini CLI in your project folder and say yes when it asks whether to trust it."),
    Agent("opencode", "opencode", "https://opencode.ai/docs/mcp-servers/", ("opencode",),
          _same("~/.config/opencode/opencode.json"), "jsonc", ("mcp",), "opencode",
          detect_paths=("~/.config/opencode",), candidates=("~/.config/opencode/opencode.jsonc",), restart="Start a new opencode session.",
          check="Run `opencode mcp list`; both servers should be listed."),
    Agent("zed", "Zed", "https://zed.dev/docs/ai/mcp", ("zed",),
          {"win": "%APPDATA%/Zed/settings.json", "mac": "~/.config/zed/settings.json",
           "linux": "~/.config/zed/settings.json"},
          "jsonc", ("context_servers",), "zed", detect_paths=("%APPDATA%/Zed", "~/.config/zed"),
          restart="Zed picks the change up by itself.",
          check="Open the Agent panel's settings; both servers should show a green dot."),
)
BY_ID = {a.id: a for a in AGENTS}


def get(agent_id: str) -> Agent:
    from .configfile import ConnectError
    if agent_id not in BY_ID:
        raise ConnectError(f"No agent called “{agent_id}”. Choose one of: {', '.join(BY_ID)}.")
    return BY_ID[agent_id]


def plat() -> str:
    return "win" if sys.platform == "win32" else "mac" if sys.platform == "darwin" else "linux"


def expand(path: str) -> Path:
    """`~`, `%APPDATA%`, `%LOCALAPPDATA%` → a real path (follows the HOME / USERPROFILE of this process)."""
    home = os.path.expanduser("~")
    roaming = os.environ.get("APPDATA") or os.path.join(home, "AppData", "Roaming")
    local = os.environ.get("LOCALAPPDATA") or os.path.join(home, "AppData", "Local")
    return Path(os.path.expanduser(path.replace("%APPDATA%", roaming).replace("%LOCALAPPDATA%", local)))


def user_file(a: Agent, generic: bool = False) -> Path:
    """The agent's settings file on this computer; `generic`: in a standard setup (the shipped guides), never this
    computer's own overrides (an environment variable's folder, a file found elsewhere)."""
    if generic:
        return expand(a.files[plat()])
    folder = os.environ.get(a.files_env[0]) if a.files_env else None
    if folder:
        return Path(folder) / a.files_env[1]
    primary = expand(a.files[plat()])
    return next((p for p in map(expand, a.candidates) if p.exists()), primary)


def to_entry(shape: str, server) -> dict:
    """One server's entry in the shape this agent's file wants."""
    env = dict(server.env)
    if shape == "opencode":
        return {"type": "local", "command": [server.command, *server.args], "environment": env, "enabled": True,
                "timeout": 30000}          # opencode waits 5 s by default; Python can start slower
    entry = {"command": server.command, "args": list(server.args), "env": env}
    return {"type": "stdio", **entry} if shape in ("claude-code", "vscode") else entry


def entry_env(entry: dict) -> dict:
    return (entry.get("env") or entry.get("environment") or {}) if isinstance(entry, dict) else {}


def render_argv(template: tuple, server, shape: str) -> list[str]:
    out: list[str] = []
    for tok in template:
        if tok == "{name}":
            out.append(server.name)
        elif tok == "{cmd}":
            out += [server.command, *server.args]
        elif tok == "{json}":
            out.append(json.dumps({"name": server.name, **to_entry("vscode", server)}))
        elif tok.startswith("{env:"):
            out += [x for k, v in server.env.items() for x in (tok[5:-1], f"{k}={v}")]
        else:
            out.append(tok)
    return out
