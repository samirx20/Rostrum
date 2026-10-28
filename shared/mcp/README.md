# shared/mcp

The conventions every app's MCP server follows: `rostrum-2d`, `rostrum-sound`, `rostrum-3d`, `rostrum-editor`. Same verbs (run / inspect / edit / render / look), same naming, same errors, same ways for an agent to see and hear its results.

Contract: [`CONVENTIONS.md`](CONVENTIONS.md). The server plumbing is code in `shared/core/` (`rostrum_core`); each app adds its own tools.

**Agents that can't attach an MCP server** call tools through [`call.py`](call.py): `python shared/mcp/call.py --name <agent> -- <server command> :: <tool> '<json args>' [:: <tool> …]`. The first command starts a background session (`call_session.py`) that keeps one MCP client session and the server running; later commands with the same `--name` and server command reuse it (about half a second a call for 2D instead of ~5–20 s), and a job started in one command is still there in the next. `:: stop` (or `--stop`) ends it; 30 min without a call ends it too; a session that died is said and replaced. `--once` runs without a session. `python shared/mcp/call.py` alone prints the full help. Every `look_*` / `render_*` tool takes `"wait": true` to answer with the finished file in the same call.
