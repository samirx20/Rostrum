# Connect Rostrum to Claude Desktop

Rostrum2D, RostrumSound, Rostrum3D each have a small server (`rostrum-2d`, `rostrum-sound`, `rostrum-3d`) that lets Claude Desktop use them. Connecting means telling Claude Desktop how to start those servers. Each starts in a fresh scratch project made for the agent, never in your own work, until the agent opens one of your projects.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to Claude Desktop and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first, never touches servers it didn't add, and **Remove** takes back only what it added.

## By hand

### Rostrum2D (`rostrum-2d`)

File: `C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json`

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

1. Open C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json (make the file if it isn't there).
2. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-2d” part, and keep your other servers.
3. Save the file.
4. Quit Claude Desktop completely (also from the tray) and open it again.
5. Click the “+” (Add files, connectors, and more) at the bottom-left of the message box, then Connectors; rostrum-2d, rostrum-sound and rostrum-3d should be listed. (The Microsoft Store version reads a different file than Settings → Developer → Edit Config opens; Rostrum uses the one the app reads.)

### RostrumSound (`rostrum-sound`)

File: `C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json`

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

1. Open C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json (make the file if it isn't there).
2. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-sound” part, and keep your other servers.
3. Save the file.
4. Quit Claude Desktop completely (also from the tray) and open it again.
5. Click the “+” (Add files, connectors, and more) at the bottom-left of the message box, then Connectors; rostrum-2d, rostrum-sound and rostrum-3d should be listed. (The Microsoft Store version reads a different file than Settings → Developer → Edit Config opens; Rostrum uses the one the app reads.)

### Rostrum3D (`rostrum-3d`)

File: `C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json`

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

1. Open C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json (make the file if it isn't there).
2. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-3d” part, and keep your other servers.
3. Save the file.
4. Quit Claude Desktop completely (also from the tray) and open it again.
5. Click the “+” (Add files, connectors, and more) at the bottom-left of the message box, then Connectors; rostrum-2d, rostrum-sound and rostrum-3d should be listed. (The Microsoft Store version reads a different file than Settings → Developer → Edit Config opens; Rostrum uses the one the app reads.)

## Check it works

Click the “+” (Add files, connectors, and more) at the bottom-left of the message box, then Connectors; rostrum-2d, rostrum-sound and rostrum-3d should be listed. (The Microsoft Store version reads a different file than Settings → Developer → Edit Config opens; Rostrum uses the one the app reads.)

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to Claude Desktop.

By hand, for Rostrum2D: open C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json and delete the “rostrum-2d” block (keep everything else).
By hand, for RostrumSound: open C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json and delete the “rostrum-sound” block (keep everything else).
By hand, for Rostrum3D: open C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json and delete the “rostrum-3d” block (keep everything else).

More about Claude Desktop and MCP servers: https://modelcontextprotocol.io/docs/develop/connect-local-servers
