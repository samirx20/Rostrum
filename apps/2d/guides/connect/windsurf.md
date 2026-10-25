# Connect Rostrum to Windsurf

Rostrum2D and RostrumSound each have a small server (`rostrum-2d`, `rostrum-sound`) that lets Windsurf use them. Connecting means telling Windsurf how to start those servers.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to Windsurf and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first, never touches servers it didn't add, and **Remove** takes back only what it added.

## By hand

### Rostrum2D (`rostrum-2d`)

File: `C:\Users\<you>\.codeium\windsurf\mcp_config.json`

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

1. Open C:\Users\<you>\.codeium\windsurf\mcp_config.json (make the file if it isn't there).
2. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-2d” part, and keep your other servers.
3. Save the file.
4. In Cascade press the refresh button next to the plugins, or restart Windsurf.
5. Open the “…” menu in the Cascade panel → MCPs; both servers should be listed. (Unsure which file your Windsurf reads? Use its “Open MCP config file” button.)

### RostrumSound (`rostrum-sound`)

File: `C:\Users\<you>\.codeium\windsurf\mcp_config.json`

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

1. Open C:\Users\<you>\.codeium\windsurf\mcp_config.json (make the file if it isn't there).
2. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-sound” part, and keep your other servers.
3. Save the file.
4. In Cascade press the refresh button next to the plugins, or restart Windsurf.
5. Open the “…” menu in the Cascade panel → MCPs; both servers should be listed. (Unsure which file your Windsurf reads? Use its “Open MCP config file” button.)

## Check it works

Open the “…” menu in the Cascade panel → MCPs; both servers should be listed. (Unsure which file your Windsurf reads? Use its “Open MCP config file” button.)

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to Windsurf.

By hand, for Rostrum2D: open C:\Users\<you>\.codeium\windsurf\mcp_config.json and delete the “rostrum-2d” block (keep everything else).
By hand, for RostrumSound: open C:\Users\<you>\.codeium\windsurf\mcp_config.json and delete the “rostrum-sound” block (keep everything else).

More about Windsurf and MCP servers: https://docs.windsurf.com/windsurf/cascade/mcp
