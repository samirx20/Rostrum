# Rostrum3D

Modelling, painting, materials, lighting, animation, simulation and rendering, built for the camera.

- **Core:** C++ (`core/`) on OpenUSD + Hydra, Cycles and the Academy Software Foundation libraries (OpenColorIO, OpenImageIO, OpenEXR, MaterialX). Prebuilt libraries from vcpkg; never build OpenUSD from source on the laptop without the manager's OK.
- **Python API** (`python/`): bindings to the core, the 3D operations on `rostrum_core`, the MCP server `rostrum-3d`.
- **Screens:** Qt Quick, from `shared/gui-kit/`. The viewport is a native Hydra view; `proofs/gui-qt/README.md` says how it plugs in.
- **Hands over:** layered OpenEXR sequences (see `shared/HANDOFFS.md`).

Nothing is built here yet. Built after 2D and Sound; the P-3D proofs (Team Hem) come first.
