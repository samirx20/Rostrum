# Connect Rostrum to VS Code

Rostrum2D, RostrumSound, Rostrum3D each have a small server (`rostrum-2d`, `rostrum-sound`, `rostrum-3d`) that lets VS Code use them. Connecting means telling VS Code how to start those servers. Each starts in a fresh scratch project made for the agent, never in your own work, until the agent opens one of your projects.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to VS Code and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first, never touches servers it didn't add, and **Remove** takes back only what it added.

## By hand

### Rostrum2D (`rostrum-2d`)

Terminal:

```
code --add-mcp '{"name": "rostrum-2d", "type": "stdio", "command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe", "args": ["-m", "rostrum2d.mcp"], "env": {"ROSTRUM_ADDED_BY": "rostrum-connect"}}'
```

File: `C:\Users\<you>\AppData\Roaming\Code\User\mcp.json`

```json
{
  "servers": {
    "rostrum-2d": {
      "type": "stdio",
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

1. Open a terminal and paste the line above, then press Enter.
2. Nothing to restart: run the command “MCP: List Servers”, pick the server and choose Start.
3. Run the command “MCP: List Servers”; all three should be listed.

### RostrumSound (`rostrum-sound`)

Terminal:

```
code --add-mcp '{"name": "rostrum-sound", "type": "stdio", "command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe", "args": ["-m", "rostrum_sound.mcp.server"], "env": {"ROSTRUM_ADDED_BY": "rostrum-connect"}}'
```

File: `C:\Users\<you>\AppData\Roaming\Code\User\mcp.json`

```json
{
  "servers": {
    "rostrum-sound": {
      "type": "stdio",
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

1. Open a terminal and paste the line above, then press Enter.
2. Nothing to restart: run the command “MCP: List Servers”, pick the server and choose Start.
3. Run the command “MCP: List Servers”; all three should be listed.

### Rostrum3D (`rostrum-3d`)

Terminal:

```
code --add-mcp '{"name": "rostrum-3d", "type": "stdio", "command": "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe", "args": ["-m", "rostrum3d.mcp"], "env": {"ROSTRUM_ADDED_BY": "rostrum-connect"}}'
```

File: `C:\Users\<you>\AppData\Roaming\Code\User\mcp.json`

```json
{
  "servers": {
    "rostrum-3d": {
      "type": "stdio",
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

1. Open a terminal and paste the line above, then press Enter.
2. Nothing to restart: run the command “MCP: List Servers”, pick the server and choose Start.
3. Run the command “MCP: List Servers”; all three should be listed.

## Check it works

Run the command “MCP: List Servers”; all three should be listed.

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to VS Code.

By hand, for Rostrum2D: open C:\Users\<you>\AppData\Roaming\Code\User\mcp.json and delete the “rostrum-2d” block (keep everything else).
By hand, for RostrumSound: open C:\Users\<you>\AppData\Roaming\Code\User\mcp.json and delete the “rostrum-sound” block (keep everything else).
By hand, for Rostrum3D: open C:\Users\<you>\AppData\Roaming\Code\User\mcp.json and delete the “rostrum-3d” block (keep everything else).

More about VS Code and MCP servers: https://code.visualstudio.com/docs/copilot/customization/mcp-servers
