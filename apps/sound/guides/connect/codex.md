# Connect Rostrum to Codex

Rostrum2D and RostrumSound each have a small server (`rostrum-2d`, `rostrum-sound`) that lets Codex use them. Connecting means telling Codex how to start those servers.

## The easy way

In Rostrum open **Help → Connect an AI agent → Add to Codex** in that app, say yes, then follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first and never touches servers it didn't add.

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
3. Run `codex mcp list`; both servers should be listed.

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
3. Run `codex mcp list`; both servers should be listed.

## Check it works

Run `codex mcp list`; both servers should be listed.

## Remove it

Easy way: Help → Connect an AI agent → Remove from Codex.

By hand, for Rostrum2D: `codex mcp remove rostrum-2d`
By hand, for RostrumSound: `codex mcp remove rostrum-sound`

More about Codex and MCP servers: https://developers.openai.com/codex/mcp
