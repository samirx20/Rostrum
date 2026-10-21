# Rostrum Editor

Story, edit, compositing, colour, final mix and delivery. The only place frames from different apps are combined (one compositor).

- **Core:** C++ (`core/`), sharing the film libraries with 3D; FFmpeg (LGPL, dynamically linked) for reading files.
- **Python API** (`python/`): the Editor's operations on `rostrum_core`, the MCP server `rostrum-editor`.
- **Screens:** Qt Quick, from `shared/gui-kit/`.
- **Takes in:** layered OpenEXR from 2D and 3D, WAV stems from Sound, all through live links (see `shared/HANDOFFS.md`).

Nothing is built here yet. Built after 2D and Sound.
