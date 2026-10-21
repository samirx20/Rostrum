# Rostrum3D

Modelling, painting, materials, lighting, animation, simulation and rendering, built for the camera.

- **Core:** C++ (`core/`, one long-lived program `rostrum3d-core serve`) on OpenUSD + Hydra, Cycles and the Academy Software Foundation libraries (OpenColorIO, OpenImageIO, OpenEXR). Built against Blender's prebuilt Windows library bundle, so OpenUSD is never built from source. How the document and USD relate, and every request: [`ENGINE_CONTRACT.md`](ENGINE_CONTRACT.md).
- **Python** (`python/`): the 3D document and operations on `rostrum_core`, the script layer, the compiler to the engine contract, the engine client, the MCP server `rostrum-3d`.
- **Screens:** Qt Quick, from `shared/gui-kit/`. The viewport is a native Hydra view; `proofs/gui-qt/README.md` says how it plugs in.
- **Hands over:** layered OpenEXR sequences (see `shared/HANDOFFS.md`).

## Build and run (H12)

- **Build** (about a minute, through the lock): `pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: 3d core build" build cmd.exe /c <worktree>\apps\3d\core\build.bat` → `apps\3d\core\.build\install\rostrum3d-core.exe`.
- **Libraries at run time:** the bundle (`ROSTRUM3D_LIBS`, default H1's download in `proofs\3d-product\.build\cycles\lib\windows_x64`), Cycles' Hydra plug-in (`proofs\3d-product\.build\cycles\install\hydra`) and our stylized plug-in (`proofs\3d-stylized\.build\install`). `rostrum3d/engine.py` sets `PATH` and `PXR_PLUGINPATH_NAME` for the child process, never loading the bundle's GPL FFmpeg or its Python. Moving these out of `proofs\` into one library folder is a next step.
- **MCP server:** `python -m rostrum3d.mcp --project <folder> --item <id>` (or the `rostrum-3d` script). Tools: the shared ones plus `look_frame`, `look_sheet`, `look_at`, `render_still`, `render_video`, `inspect_usd_file`, `inspect_shot`. Agents' guide: `python/rostrum3d/guides/agents.md`.

## Layout

| Part | Files |
|---|---|
| Core: requests, Hydra, colour, memory | `core/src/main.cpp`, `serve.*`, `requests.*`, `args.h`, `hydra.*` (one engine per renderer, progressive loop, pick), `gl_context.*` (hidden GL 4.6 context, float framebuffer), `image_out.*` (EXR; OCIO PNG; `.partial` then rename), `gpu_mem.*` (DXGI + NVML), `inspect.*` |
| Core: scene → USD | `core/src/stage_build.*`, `stage_items.*`, `item_track.h` (per-frame samples), `primitives.*`, `materials.*`, `lights_cameras.cpp`, `json_read.h` |
| Python | `python/rostrum3d/`: `fields.py` (the one table), `kind.py`, `ops_*.py`, `build.py`, `aim.py`, `script.py`, `compile.py`, `engine.py`, `mcp/` |

## Open

- Storm draws glass as solid light grey (the preview surface's opacity isn't honoured); Cycles is right. Viewport-only.
- Storm with the scene's lights only: no studio environment or exposure control for the viewport yet (as P-GUI found).
- The stylized renderer takes no look settings through the contract yet.
- Imports in other units (e.g. centimetres) are not rescaled; the import's scale must be set.

## Python layer (`python/rostrum3d/`, H12)

The document, its operations, the script layer and the compiler to the engine's scene description: see [`DOCUMENT.md`](DOCUMENT.md) and [`ENGINE_CONTRACT.md`](ENGINE_CONTRACT.md). Install: `uv pip install --python <worktree>\.venv\Scripts\python.exe -e apps\3d\python`.

**Shared-layer request (for Team Sam):** the key model's easing table and evaluator (`rostrum2d/easing.py`, `rostrum2d/evaluate.py`) and the key operations (`key.add`, `key.remove`, `value.set`, `key.clear`, now written once per app in `rostrum2d/ops_keys.py` and `rostrum3d/ops_keys.py`) should move to `rostrum_core`, so every app shares one copy. Until then `rostrum3d` imports the easing and evaluator from `rostrum2d`.
