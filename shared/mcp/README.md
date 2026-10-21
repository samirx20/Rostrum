# shared/mcp

The conventions every app's MCP server follows: `rostrum-2d`, `rostrum-sound`, `rostrum-3d`, `rostrum-editor`. Same verbs (run / inspect / edit / render / look), same naming, same errors, same ways for an agent to see and hear its results.

Contract: [`CONVENTIONS.md`](CONVENTIONS.md). The server plumbing is code in `shared/core/` (`rostrum_core`); each app adds its own tools.
