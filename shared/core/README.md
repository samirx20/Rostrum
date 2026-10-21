# shared/core — `rostrum_core`, the shared Python core

What all four apps' Python layers share, so each idea has one source of truth:

- **Operations:** one format for every change, from the GUI, a script or an agent.
- **History:** one history per document: undo, versions, who changed what.
- **Registry:** every operation is registered once with its description and arguments; the GUI inspector, the command bar, the CLI and the MCP tool lists are all built from it.
- **MCP plumbing:** the server loop, errors, jobs and the "look" helpers each app's MCP server builds on (conventions: `../mcp/CONVENTIONS.md`).
- **Project-service client:** markers, links, the cache and the jobs queue (`../project-service/CONTRACT.md`).

Layout once code starts (Stage 2): `shared/core/rostrum_core/` (the package) and `shared/core/tests/`. Each app depends on it as a local package.

Contract: [`OPERATIONS.md`](OPERATIONS.md). No code yet.
