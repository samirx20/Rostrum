# Connecting coding agents to Rostrum

`rostrum_connect` (this folder) puts Rostrum2D's server (`rostrum-2d`) and RostrumSound's server (`rostrum-sound`) into a person's coding agent, each agent in its own way. The table below is written from the data in `rostrum_connect/agents.py` (`python -m rostrum_connect table`); change the data, not this page by hand. Sources: each agent's own docs (the Docs column), checked 2026-10-22.

```
python -m rostrum_connect found | status | add --agent A --app 2d|sound [--yes] | remove … | entries --agent A | hand --agent A --app … | guides --out <folder>
```

| Agent | Added with | Settings file (Windows) | Table key | Needs a restart? | Docs |
|---|---|---|---|---|---|
| Claude Code | `claude mcp add …` | `~/.claude.json` | `mcpServers` (json) | Start a new Claude Code session (servers load when it starts). | https://code.claude.com/docs/en/mcp |
| Claude Desktop | file edit | `%APPDATA%/Claude/claude_desktop_config.json` | `mcpServers` (json) | Quit Claude Desktop completely (also from the tray) and open it again. | https://modelcontextprotocol.io/docs/develop/connect-local-servers |
| Codex | `codex mcp add …` | `~/.codex/config.toml` | `mcp_servers` (toml) | Start a new Codex session. | https://developers.openai.com/codex/mcp |
| Cursor | file edit (or link) | `~/.cursor/mcp.json` | `mcpServers` (json) | Quit Cursor and open it again. | https://cursor.com/docs/context/mcp |
| VS Code | `code --add-mcp …`, or file edit | `%APPDATA%/Code/User/mcp.json` | `servers` (jsonc) | Nothing to restart: run the command “MCP: List Servers”, pick the server and choose Start. | https://code.visualstudio.com/docs/copilot/customization/mcp-servers |
| Windsurf | file edit | `~/.codeium/windsurf/mcp_config.json` | `mcpServers` (json) | In Cascade press the refresh button next to the plugins, or restart Windsurf. | https://docs.windsurf.com/windsurf/cascade/mcp |
| Antigravity | file edit | `~/.gemini/config/mcp_config.json` | `mcpServers` (json) | In Antigravity: Agent panel “…” → MCP Servers → Manage MCP Servers → Refresh (or start a new `agy` session). | https://codelabs.developers.google.com/google-workspace-mcp-antigravity |
| opencode | file edit | `~/.config/opencode/opencode.json` | `mcp` (jsonc) | Start a new opencode session. | https://opencode.ai/docs/mcp-servers/ |
| Zed | file edit | `%APPDATA%/Zed/settings.json` | `context_servers` (jsonc) | Zed picks the change up by itself. | https://zed.dev/docs/ai/mcp |


## Rules the code follows

- Every entry Rostrum adds carries `ROSTRUM_ADDED_BY=rostrum-connect` in its environment. Only entries with that marker are ever replaced or removed; a `rostrum-2d` without it is someone else's and is reported, never touched.
- The agent's own command is used when it is on the PATH and has one (Claude Code, Codex, VS Code add). Otherwise the settings file is edited by structure (JSON, JSONC, TOML via tomlkit), never by text replace.
- The file is copied to `%LOCALAPPDATA%\Rostrum\agent-backups\<agent>\` before any change. A file with comments (JSONC) is refused, not rewritten. A file that can't be read is left alone.
- Success is only reported after the file is read again and shows the entry.

## Things that differ from what people expect

- **Claude Code**: the default scope is "local" (one project), so Rostrum always passes `--scope user`. `--env` swallows the next word, so `--transport stdio` sits between it and the name. With `CLAUDE_CONFIG_DIR` set, the file is `<dir>/.claude.json`.
- **Antigravity** (replaces Gemini CLI, which Google stopped for personal accounts on 2026-06-18, so it is not listed): the file is `~/.gemini/config/mcp_config.json`; remote servers there use `serverUrl`, local ones `command` + `args`. Sam's app reads this file, not `~/.gemini/antigravity/mcp_config.json`, which is used only when the `~/.gemini/config` folder does not exist; “View raw config” in Antigravity shows the live file. A server someone put in by hand that runs our module (`-m rostrum2d.mcp`) counts as added (`know_by_module`). The file also holds other servers and tokens: never print or log it.
- **Claude Desktop**: the Microsoft Store version reads `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Roaming\Claude\claude_desktop_config.json`, not the file "Edit Config" opens. Rostrum uses the Store file when it exists.
- **Windsurf**: its docs moved to Devin's site and now name `%APPDATA%\devin\mcp_config.json`; older installs read `~/.codeium/windsurf/mcp_config.json`. Rostrum uses whichever exists (devin first), else the `.codeium` one. Windsurf's “Open MCP config file” button shows the live path.
- **VS Code**: `code --add-mcp` only adds (to the user profile); removing is a file edit. The user `mcp.json` path is inferred from VS Code's folder layout, not documented.
- **opencode**: no non-interactive add or remove, so always a file edit. `command` is one list, the environment key is `environment`, and Rostrum sets `timeout` to 30 s (the default is 5 s).
- **Cursor**: also has a one-click link (base64 of the entry). **Zed**: the Windows settings path isn't documented.
- **Codex**: project `.codex/config.toml` only works in trusted projects; Rostrum edits the user file.
