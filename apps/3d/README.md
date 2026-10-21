# Rostrum3D

Modelling, painting, materials, lighting, animation, simulation and rendering, built for the camera.

- **Core:** C++ (`core/`) on OpenUSD + Hydra, Cycles and the Academy Software Foundation libraries (OpenColorIO, OpenImageIO, OpenEXR, MaterialX). Prebuilt libraries from vcpkg; never build OpenUSD from source on the laptop without the manager's OK.
- **Python API** (`python/`): bindings to the core, the 3D operations on `rostrum_core`, the MCP server `rostrum-3d`.
- **Screens:** Qt Quick, from `shared/gui-kit/`. The viewport is a native Hydra view; `proofs/gui-qt/README.md` says how it plugs in.
- **Hands over:** layered OpenEXR sequences (see `shared/HANDOFFS.md`).

Nothing is built here yet. Built after 2D and Sound; the P-3D proofs (Team Hem) come first.

## Python layer (`python/rostrum3d/`, H12)

The document, its operations, the script layer and the compiler to the engine's scene description: see [`DOCUMENT.md`](DOCUMENT.md) and [`ENGINE_CONTRACT.md`](ENGINE_CONTRACT.md). Install: `uv pip install --python <worktree>\.venv\Scripts\python.exe -e apps\3d\python`.

**Shared-layer request (for Team Sam):** the key model's easing table and evaluator (`rostrum2d/easing.py`, `rostrum2d/evaluate.py`) and the key operations (`key.add`, `key.remove`, `value.set`, `key.clear`, now written once per app in `rostrum2d/ops_keys.py` and `rostrum3d/ops_keys.py`) should move to `rostrum_core`, so every app shares one copy. Until then `rostrum3d` imports the easing and evaluator from `rostrum2d`.
