# Connect Rostrum to opencode

Rostrum2D, RostrumSound, Rostrum3D each have a small server (`rostrum-2d`, `rostrum-sound`, `rostrum-3d`) that lets opencode use them. Connecting means telling opencode how to start those servers. Each starts in a fresh scratch project made for the agent, never in your own work, until the agent opens one of your projects.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to opencode and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first, never touches servers it didn't add, and **Remove** takes back only what it added.

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
5. Run `opencode mcp list`; all three servers should be listed.

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
5. Run `opencode mcp list`; all three servers should be listed.

### Rostrum3D (`rostrum-3d`)

File: `C:\Users\<you>\.config\opencode\opencode.json`

```json
{
  "mcp": {
    "rostrum-3d": {
      "type": "local",
      "command": [
        "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe",
        "-m",
        "rostrum3d.mcp"
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
2. Paste the block above inside “mcp”. If “mcp” is already there, add only the “rostrum-3d” part, and keep your other servers.
3. Save the file. (It may hold comments: keep them. Rostrum's button refuses such a file rather than lose them.)
4. Start a new opencode session.
5. Run `opencode mcp list`; all three servers should be listed.

## Check it works

Run `opencode mcp list`; all three servers should be listed.

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to opencode.

By hand, for Rostrum2D: open C:\Users\<you>\.config\opencode\opencode.json and delete the “rostrum-2d” block (keep everything else).
By hand, for RostrumSound: open C:\Users\<you>\.config\opencode\opencode.json and delete the “rostrum-sound” block (keep everything else).
By hand, for Rostrum3D: open C:\Users\<you>\.config\opencode\opencode.json and delete the “rostrum-3d” block (keep everything else).

More about opencode and MCP servers: https://opencode.ai/docs/mcp-servers/
