# Connect Rostrum to Claude Code

Rostrum2D, RostrumSound, Rostrum3D each have a small server (`rostrum-2d`, `rostrum-sound`, `rostrum-3d`) that lets Claude Code use them. Connecting means telling Claude Code how to start those servers. Each starts in a fresh scratch project made for the agent, never in your own work, until the agent opens one of your projects.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to Claude Code and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first, never touches servers it didn't add, and **Remove** takes back only what it added.

## By hand

### Rostrum2D (`rostrum-2d`)

Terminal:

```
claude mcp add --scope user -e ROSTRUM_ADDED_BY=rostrum-connect --transport stdio rostrum-2d -- 'C:\Users\<you>\AppData\Local\Programs\Rostrum\runtime\python\python.exe' -m rostrum2d.mcp
```

File: `C:\Users\<you>\.claude.json`

```json
{
  "mcpServers": {
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
2. Start a new Claude Code session (servers load when it starts).
3. In Claude Code type /mcp (or run `claude mcp list`); rostrum-2d, rostrum-sound and rostrum-3d should be listed as connected.

### RostrumSound (`rostrum-sound`)

Terminal:

```
claude mcp add --scope user -e ROSTRUM_ADDED_BY=rostrum-connect --transport stdio rostrum-sound -- 'C:\Users\<you>\AppData\Local\Programs\Rostrum\runtime\python\python.exe' -m rostrum_sound.mcp.server
```

File: `C:\Users\<you>\.claude.json`

```json
{
  "mcpServers": {
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
2. Start a new Claude Code session (servers load when it starts).
3. In Claude Code type /mcp (or run `claude mcp list`); rostrum-2d, rostrum-sound and rostrum-3d should be listed as connected.

### Rostrum3D (`rostrum-3d`)

Terminal:

```
claude mcp add --scope user -e ROSTRUM_ADDED_BY=rostrum-connect --transport stdio rostrum-3d -- 'C:\Users\<you>\AppData\Local\Programs\Rostrum\runtime\python\python.exe' -m rostrum3d.mcp
```

File: `C:\Users\<you>\.claude.json`

```json
{
  "mcpServers": {
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
2. Start a new Claude Code session (servers load when it starts).
3. In Claude Code type /mcp (or run `claude mcp list`); rostrum-2d, rostrum-sound and rostrum-3d should be listed as connected.

## Agents started by a launcher (one folder per account)

A launcher that runs Claude Code once per account (Agent Hub) gives every account its own settings folder, and Claude Code there reads only that folder's `.claude.json`, not the file above. Add Rostrum to all of them at once:

```
python -m rostrum_connect add --agent claude-code --everywhere --yes
```

`python -m rostrum_connect profiles` lists the folders it found.

## Check it works

In Claude Code type /mcp (or run `claude mcp list`); rostrum-2d, rostrum-sound and rostrum-3d should be listed as connected.

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to Claude Code.

By hand, for Rostrum2D: `claude mcp remove --scope user rostrum-2d`
By hand, for RostrumSound: `claude mcp remove --scope user rostrum-sound`
By hand, for Rostrum3D: `claude mcp remove --scope user rostrum-3d`

More about Claude Code and MCP servers: https://code.claude.com/docs/en/mcp
