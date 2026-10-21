# shared/ — the layer all four apps stand on

Owned by Team Sam. Other teams ask for changes in their report; Team Sam makes them, alone, and they merge first.

| Folder / file | What it is |
|---|---|
| `core/` | **The shared Python core, package `rostrum_core`.** Operations, the one history, the operation registry, MCP server plumbing, the project-service client. Every app's Python layer imports it. Contract: `core/OPERATIONS.md`. |
| `project-service/` | The small background program all apps talk to: project items, shared markers, live links, the content-keyed cache, the one jobs queue. Contract: `project-service/CONTRACT.md`. |
| `mcp/` | The conventions every app's MCP server follows (run / inspect / edit / render / look). Contract: `mcp/CONVENTIONS.md`. The code that serves them lives in `core/`. |
| `gui-kit/` | The one Qt Quick UI kit: look, panels, inspector, timeline, command bar. Shaped by the GUI proof (`proofs/gui-qt/`). |
| `painting-kit/` | The one brush engine and the agent painting tools (strokes, seeing the canvas, where each stroke lands). |
| `HANDOFFS.md` | How apps hand pictures and sound to each other: layered OpenEXR, WAV stems, OpenColorIO, the project folder. |

Engines (Rust for 2D and Sound, C++ for 3D and the Editor) never own the document: the Python layer does, through `rostrum_core`.
