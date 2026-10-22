# Connect Rostrum to opencode

Rostrum2D and RostrumSound each have a small server (`rostrum-2d`, `rostrum-sound`) that lets opencode use them. Connecting means telling opencode how to start those servers.

## The easy way

In Rostrum open **Help → Connect an AI agent → Add to opencode** in that app, say yes, then follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first and never touches servers it didn't add.

## By hand

### Rostrum2D (`rostrum-2d`)

File: `C:\Users\<you>\.config\opencode\opencode.json`

```json
{
  "mcp": {
    "rostrum-2d": {
      "type": "local",
      "command": [
        "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe",
        "-m",
        "rostrum2d.mcp"
      ],
      "environment": {
        "ROSTRUM_ADDED_BY": "rostrum-connect"
      },
      "enabled": true,
      "timeout": 30000
    }
  }
}
```

1. Open C:\Users\<you>\.config\opencode\opencode.json (make the file if it isn't there).
2. Paste the block above inside “mcp”. If “mcp” is already there, add only the “rostrum-2d” part, and keep your other servers.
3. Save the file. (It may hold comments: keep them. Rostrum's button refuses such a file rather than lose them.)
4. Start a new opencode session.
5. Run `opencode mcp list`; both servers should be listed.

### RostrumSound (`rostrum-sound`)

File: `C:\Users\<you>\.config\opencode\opencode.json`

```json
{
  "mcp": {
    "rostrum-sound": {
      "type": "local",
      "command": [
        "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe",
        "-m",
        "rostrum_sound.mcp.server"
      ],
      "environment": {
        "ROSTRUM_ADDED_BY": "rostrum-connect"
      },
      "enabled": true,
      "timeout": 30000
    }
  }
}
```

1. Open C:\Users\<you>\.config\opencode\opencode.json (make the file if it isn't there).
2. Paste the block above inside “mcp”. If “mcp” is already there, add only the “rostrum-sound” part, and keep your other servers.
3. Save the file. (It may hold comments: keep them. Rostrum's button refuses such a file rather than lose them.)
4. Start a new opencode session.
5. Run `opencode mcp list`; both servers should be listed.

## Check it works

Run `opencode mcp list`; both servers should be listed.

## Remove it

Easy way: Help → Connect an AI agent → Remove from opencode.

By hand, for Rostrum2D: open C:\Users\<you>\.config\opencode\opencode.json and delete the “rostrum-2d” block (keep everything else).
By hand, for RostrumSound: open C:\Users\<you>\.config\opencode\opencode.json and delete the “rostrum-sound” block (keep everything else).

More about opencode and MCP servers: https://opencode.ai/docs/mcp-servers/
