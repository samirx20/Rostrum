# Connect Rostrum to Codex

Rostrum2D, RostrumSound, Rostrum3D each have a small server (`rostrum-2d`, `rostrum-sound`, `rostrum-3d`) that lets Codex use them. Connecting means telling Codex how to start those servers. Each starts in a fresh scratch project made for the agent, never in your own work, until the agent opens one of your projects.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to Codex and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first, never touches servers it didn't add, and **Remove** takes back only what it added.

## By hand

### Rostrum2D (`rostrum-2d`)

Terminal:

```
codex mcp add rostrum-2d --env ROSTRUM_ADDED_BY=rostrum-connect -- 'C:\Users\<you>\AppData\Local\Programs\Rostrum\runtime\python\python.exe' -m rostrum2d.mcp
```

File: `C:\Users\<you>\.codex\config.toml`

```toml
[mcp_servers.rostrum-2d]
command = "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe"
args = ["-m", "rostrum2d.mcp"]

[mcp_servers.rostrum-2d.env]
ROSTRUM_ADDED_BY = "rostrum-connect"
```

1. Open a terminal and paste the line above, then press Enter.
2. Start a new Codex session.
3. Run `codex mcp list`; all three servers should be listed.

### RostrumSound (`rostrum-sound`)

Terminal:

```
codex mcp add rostrum-sound --env ROSTRUM_ADDED_BY=rostrum-connect -- 'C:\Users\<you>\AppData\Local\Programs\Rostrum\runtime\python\python.exe' -m rostrum_sound.mcp.server
```

File: `C:\Users\<you>\.codex\config.toml`

```toml
[mcp_servers.rostrum-sound]
command = "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe"
args = ["-m", "rostrum_sound.mcp.server"]

[mcp_servers.rostrum-sound.env]
ROSTRUM_ADDED_BY = "rostrum-connect"
```

1. Open a terminal and paste the line above, then press Enter.
2. Start a new Codex session.
3. Run `codex mcp list`; all three servers should be listed.

### Rostrum3D (`rostrum-3d`)

Terminal:

```
codex mcp add rostrum-3d --env ROSTRUM_ADDED_BY=rostrum-connect -- 'C:\Users\<you>\AppData\Local\Programs\Rostrum\runtime\python\python.exe' -m rostrum3d.mcp
```

File: `C:\Users\<you>\.codex\config.toml`

```toml
[mcp_servers.rostrum-3d]
command = "C:\\Users\\<you>\\AppData\\Local\\Programs\\Rostrum\\runtime\\python\\python.exe"
args = ["-m", "rostrum3d.mcp"]

[mcp_servers.rostrum-3d.env]
ROSTRUM_ADDED_BY = "rostrum-connect"
```

1. Open a terminal and paste the line above, then press Enter.
2. Start a new Codex session.
3. Run `codex mcp list`; all three servers should be listed.

## Agents started by a launcher (one folder per account)

A launcher that runs Codex once per account (Agent Hub) gives every account its own settings folder, and Codex there reads only that folder's `config.toml`, not the file above. Add Rostrum to all of them at once:

```
python -m rostrum_connect add --agent codex --everywhere --yes
```

`python -m rostrum_connect profiles` lists the folders it found.

## Check it works

Run `codex mcp list`; all three servers should be listed.

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to Codex.

By hand, for Rostrum2D: `codex mcp remove rostrum-2d`
By hand, for RostrumSound: `codex mcp remove rostrum-sound`
By hand, for Rostrum3D: `codex mcp remove rostrum-3d`

More about Codex and MCP servers: https://developers.openai.com/codex/mcp
