# Connect Rostrum to Zed

Rostrum2D, RostrumSound, Rostrum3D each have a small server (`rostrum-2d`, `rostrum-sound`, `rostrum-3d`) that lets Zed use them. Connecting means telling Zed how to start those servers. Each starts in a fresh scratch project made for the agent, never in your own work, until the agent opens one of your projects.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to Zed and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first, never touches servers it didn't add, and **Remove** takes back only what it added.

## By hand

### Rostrum2D (`rostrum-2d`)

File: `C:\Users\<you>\AppData\Roaming\Zed\settings.json`

```json
{
  "context_servers": {
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

1. Open C:\Users\<you>\AppData\Roaming\Zed\settings.json (make the file if it isn't there).
2. Paste the block above inside “context_servers”. If “context_servers” is already there, add only the “rostrum-2d” part, and keep your other servers.
3. Save the file. (It may hold comments: keep them. Rostrum's button refuses such a file rather than lose them.)
4. Zed picks the change up by itself.
5. Open the Agent panel's settings; all three servers should show a green dot.

### RostrumSound (`rostrum-sound`)

File: `C:\Users\<you>\AppData\Roaming\Zed\settings.json`

```json
{
  "context_servers": {
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

1. Open C:\Users\<you>\AppData\Roaming\Zed\settings.json (make the file if it isn't there).
2. Paste the block above inside “context_servers”. If “context_servers” is already there, add only the “rostrum-sound” part, and keep your other servers.
3. Save the file. (It may hold comments: keep them. Rostrum's button refuses such a file rather than lose them.)
4. Zed picks the change up by itself.
5. Open the Agent panel's settings; all three servers should show a green dot.

### Rostrum3D (`rostrum-3d`)

File: `C:\Users\<you>\AppData\Roaming\Zed\settings.json`

```json
{
  "context_servers": {
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

1. Open C:\Users\<you>\AppData\Roaming\Zed\settings.json (make the file if it isn't there).
2. Paste the block above inside “context_servers”. If “context_servers” is already there, add only the “rostrum-3d” part, and keep your other servers.
3. Save the file. (It may hold comments: keep them. Rostrum's button refuses such a file rather than lose them.)
4. Zed picks the change up by itself.
5. Open the Agent panel's settings; all three servers should show a green dot.

## Check it works

Open the Agent panel's settings; all three servers should show a green dot.

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to Zed.

By hand, for Rostrum2D: open C:\Users\<you>\AppData\Roaming\Zed\settings.json and delete the “rostrum-2d” block (keep everything else).
By hand, for RostrumSound: open C:\Users\<you>\AppData\Roaming\Zed\settings.json and delete the “rostrum-sound” block (keep everything else).
By hand, for Rostrum3D: open C:\Users\<you>\AppData\Roaming\Zed\settings.json and delete the “rostrum-3d” block (keep everything else).

More about Zed and MCP servers: https://zed.dev/docs/ai/mcp
