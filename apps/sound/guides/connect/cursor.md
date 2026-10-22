# Connect Rostrum to Cursor

Rostrum2D and RostrumSound each have a small server (`rostrum-2d`, `rostrum-sound`) that lets Cursor use them. Connecting means telling Cursor how to start those servers.

## The easy way

In Rostrum click the **?** button in the top bar and choose **Connect an AI agent…**. Press **Add** next to Cursor, then **Add** again to say yes, and follow the last line it shows (restart or check). Rostrum keeps a copy of your settings file first and never touches servers it didn't add.

## By hand

### Rostrum2D (`rostrum-2d`)

Link: cursor://anysphere.cursor-deeplink/mcp/install?name=rostrum-2d&config=eyJjb21tYW5kIjoiQzpcXFVzZXJzXFw8eW91PlxcQXBwRGF0YVxcTG9jYWxcXFByb2dyYW1zXFxSb3N0cnVtXFxydW50aW1lXFxweXRob25cXHB5dGhvbi5leGUiLCJhcmdzIjpbIi1tIiwicm9zdHJ1bTJkLm1jcCJdLCJlbnYiOnsiUk9TVFJVTV9BRERFRF9CWSI6InJvc3RydW0tY29ubmVjdCJ9fQ==

File: `C:\Users\<you>\.cursor\mcp.json`

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

1. Quickest: open the link above; Cursor asks you to confirm.
2. Open C:\Users\<you>\.cursor\mcp.json (make the file if it isn't there).
3. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-2d” part, and keep your other servers.
4. Save the file.
5. Quit Cursor and open it again.
6. Look under Customize in Cursor's sidebar; both servers should be listed with their switch on.

### RostrumSound (`rostrum-sound`)

Link: cursor://anysphere.cursor-deeplink/mcp/install?name=rostrum-sound&config=eyJjb21tYW5kIjoiQzpcXFVzZXJzXFw8eW91PlxcQXBwRGF0YVxcTG9jYWxcXFByb2dyYW1zXFxSb3N0cnVtXFxydW50aW1lXFxweXRob25cXHB5dGhvbi5leGUiLCJhcmdzIjpbIi1tIiwicm9zdHJ1bV9zb3VuZC5tY3Auc2VydmVyIl0sImVudiI6eyJST1NUUlVNX0FEREVEX0JZIjoicm9zdHJ1bS1jb25uZWN0In19

File: `C:\Users\<you>\.cursor\mcp.json`

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

1. Quickest: open the link above; Cursor asks you to confirm.
2. Open C:\Users\<you>\.cursor\mcp.json (make the file if it isn't there).
3. Paste the block above inside “mcpServers”. If “mcpServers” is already there, add only the “rostrum-sound” part, and keep your other servers.
4. Save the file.
5. Quit Cursor and open it again.
6. Look under Customize in Cursor's sidebar; both servers should be listed with their switch on.

## Check it works

Look under Customize in Cursor's sidebar; both servers should be listed with their switch on.

## Remove it

Easy way: **?** → **Connect an AI agent…**, then press **Remove** next to Cursor.

By hand, for Rostrum2D: open C:\Users\<you>\.cursor\mcp.json and delete the “rostrum-2d” block (keep everything else).
By hand, for RostrumSound: open C:\Users\<you>\.cursor\mcp.json and delete the “rostrum-sound” block (keep everything else).

More about Cursor and MCP servers: https://cursor.com/docs/context/mcp
