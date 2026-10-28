# Connect Rostrum to Antigravity

Rostrum2D, RostrumSound, Rostrum3D each have a small server (`rostrum-2d`, `rostrum-sound`, `rostrum-3d`) that lets Antigravity use them. Connecting means telling Antigravity how to start those servers. Each starts in a fresh scratch project made for the agent, never in your own work, until the agent opens one of your projects.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to Antigravity and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first, never touches servers it didn't add, and **Remove** takes back only what it added.

## By hand

### Rostrum2D (`rostrum-2d`)

File: `C:\Users\<you>\.gemini\config\mcp_config.json`

```json
{
  "mcpServers": {
    "rostrum-2d": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe",
      "args": [
        "-m",
        "rostrum2d.mcp"
      ],
      "env": {
        "ROSTRUM_ADDED_BY": "rostrum-connect"
      }
    }
  }
}
```

1. Open C:\Users\<you>\.gemini\config\mcp_config.json (make the file if it isn't there).
2. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-2d” part, and keep your other servers.
3. Save the file.
4. In Antigravity open the “…” menu of the Agent panel → MCP Servers → Manage MCP Servers and press Refresh (or start a new `agy` session).
5. In the Agent panel's “…” menu choose MCP Servers → Manage MCP Servers (or type /mcp in `agy`); rostrum-2d, rostrum-sound and rostrum-3d should be listed. “View raw config” shows the file Antigravity reads.

### RostrumSound (`rostrum-sound`)

File: `C:\Users\<you>\.gemini\config\mcp_config.json`

```json
{
  "mcpServers": {
    "rostrum-sound": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe",
      "args": [
        "-m",
        "rostrum_sound.mcp.server"
      ],
      "env": {
        "ROSTRUM_ADDED_BY": "rostrum-connect"
      }
    }
  }
}
```

1. Open C:\Users\<you>\.gemini\config\mcp_config.json (make the file if it isn't there).
2. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-sound” part, and keep your other servers.
3. Save the file.
4. In Antigravity open the “…” menu of the Agent panel → MCP Servers → Manage MCP Servers and press Refresh (or start a new `agy` session).
5. In the Agent panel's “…” menu choose MCP Servers → Manage MCP Servers (or type /mcp in `agy`); rostrum-2d, rostrum-sound and rostrum-3d should be listed. “View raw config” shows the file Antigravity reads.

### Rostrum3D (`rostrum-3d`)

File: `C:\Users\<you>\.gemini\config\mcp_config.json`

```json
{
  "mcpServers": {
    "rostrum-3d": {
      "command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe",
      "args": [
        "-m",
        "rostrum3d.mcp"
      ],
      "env": {
        "ROSTRUM_ADDED_BY": "rostrum-connect"
      }
    }
  }
}
```

1. Open C:\Users\<you>\.gemini\config\mcp_config.json (make the file if it isn't there).
2. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-3d” part, and keep your other servers.
3. Save the file.
4. In Antigravity open the “…” menu of the Agent panel → MCP Servers → Manage MCP Servers and press Refresh (or start a new `agy` session).
5. In the Agent panel's “…” menu choose MCP Servers → Manage MCP Servers (or type /mcp in `agy`); rostrum-2d, rostrum-sound and rostrum-3d should be listed. “View raw config” shows the file Antigravity reads.

## Agents started by a launcher (one folder per account)

A launcher that runs Antigravity once per account (Agent Hub) gives every account its own settings folder, and Antigravity there reads only that folder's `config/mcp_config.json`, not the file above. Add Rostrum to all of them at once:

```
python -m rostrum_connect add --agent antigravity --everywhere --yes
```

`python -m rostrum_connect profiles` lists the folders it found.

## Check it works

In the Agent panel's “…” menu choose MCP Servers → Manage MCP Servers (or type /mcp in `agy`); rostrum-2d, rostrum-sound and rostrum-3d should be listed. “View raw config” shows the file Antigravity reads.

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to Antigravity.

By hand, for Rostrum2D: open C:\Users\<you>\.gemini\config\mcp_config.json and delete the “rostrum-2d” block (keep everything else).
By hand, for RostrumSound: open C:\Users\<you>\.gemini\config\mcp_config.json and delete the “rostrum-sound” block (keep everything else).
By hand, for Rostrum3D: open C:\Users\<you>\.gemini\config\mcp_config.json and delete the “rostrum-3d” block (keep everything else).

More about Antigravity and MCP servers: https://codelabs.developers.google.com/google-workspace-mcp-antigravity
