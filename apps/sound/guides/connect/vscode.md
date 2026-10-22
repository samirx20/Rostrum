# Connect Rostrum to VS Code

Rostrum2D and RostrumSound each have a small server (`rostrum-2d`, `rostrum-sound`) that lets VS Code use them. Connecting means telling VS Code how to start those servers.

## The easy way

In Rostrum open **Help → Connect an AI agent → Add to VS Code** in that app, say yes, then follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first and never touches servers it didn't add.

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
3. Run the command “MCP: List Servers”; both should be listed.

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
3. Run the command “MCP: List Servers”; both should be listed.

## Check it works

Run the command “MCP: List Servers”; both should be listed.

## Remove it

Easy way: Help → Connect an AI agent → Remove from VS Code.

By hand, for Rostrum2D: open C:\Users\<you>\AppData\Roaming\Code\User\mcp.json and delete the “rostrum-2d” block (keep everything else).
By hand, for RostrumSound: open C:\Users\<you>\AppData\Roaming\Code\User\mcp.json and delete the “rostrum-sound” block (keep everything else).

More about VS Code and MCP servers: https://code.visualstudio.com/docs/copilot/customization/mcp-servers
