# Connect Rostrum to Gemini CLI

Rostrum2D and RostrumSound each have a small server (`rostrum-2d`, `rostrum-sound`) that lets Gemini CLI use them. Connecting means telling Gemini CLI how to start those servers.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to Gemini CLI and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first, never touches servers it didn't add, and **Remove** takes back only what it added.

## By hand

### Rostrum2D (`rostrum-2d`)

Terminal:

```
gemini mcp add -e ROSTRUM_ADDED_BY=rostrum-connect -s user rostrum-2d 'C:\Users\<you>\AppData\Local\Programs\Rostrum\runtime\python\python.exe' -m rostrum2d.mcp
```

File: `C:\Users\<you>\.gemini\settings.json`

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

1. Open a terminal and paste the line above, then press Enter.
2. Start a new Gemini CLI session.
3. In Gemini CLI type /mcp (or run `gemini mcp list`); both should be listed. Gemini switches every such server off in a folder you haven't trusted (it then says Disabled): start Gemini CLI in your project folder and say yes when it asks whether to trust it.

### RostrumSound (`rostrum-sound`)

Terminal:

```
gemini mcp add -e ROSTRUM_ADDED_BY=rostrum-connect -s user rostrum-sound 'C:\Users\<you>\AppData\Local\Programs\Rostrum\runtime\python\python.exe' -m rostrum_sound.mcp.server
```

File: `C:\Users\<you>\.gemini\settings.json`

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

1. Open a terminal and paste the line above, then press Enter.
2. Start a new Gemini CLI session.
3. In Gemini CLI type /mcp (or run `gemini mcp list`); both should be listed. Gemini switches every such server off in a folder you haven't trusted (it then says Disabled): start Gemini CLI in your project folder and say yes when it asks whether to trust it.

## Check it works

In Gemini CLI type /mcp (or run `gemini mcp list`); both should be listed. Gemini switches every such server off in a folder you haven't trusted (it then says Disabled): start Gemini CLI in your project folder and say yes when it asks whether to trust it.

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to Gemini CLI.

By hand, for Rostrum2D: `gemini mcp remove -s user rostrum-2d`
By hand, for RostrumSound: `gemini mcp remove -s user rostrum-sound`

More about Gemini CLI and MCP servers: https://geminicli.com/docs/tools/mcp-server/
