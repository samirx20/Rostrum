# Rostrum3D

Modelling, painting, materials, lighting, animation, simulation and rendering, built for the camera.

- **Core:** C++ (`core/`, one long-lived program `rostrum3d-core serve`) on OpenUSD + Hydra, Cycles and the Academy Software Foundation libraries (OpenColorIO, OpenImageIO, OpenEXR). Built against Blender's prebuilt Windows library bundle, so OpenUSD is never built from source. How the document and USD relate, and every request: [`ENGINE_CONTRACT.md`](ENGINE_CONTRACT.md).
- **Python** (`python/`): the 3D document and operations on `rostrum_core`, the script layer, the compiler to the engine contract, the engine client, the MCP server `rostrum-3d`.
- **Screen** (`app/`, H13): Qt Quick on `shared/gui-kit/`: outliner, live Storm viewport (orbit, pan, zoom, look through the shot camera, click to select with an outline, studio light, exposure), inspector built from the field operations, full-width timeline, Render button. See [`app/README.md`](app/README.md). The viewport's pictures come from the core's `view` request (ENGINE_CONTRACT.md § 4) through shared memory, from the same kind of core process as every render.
- **Hands over:** layered OpenEXR sequences (see `shared/HANDOFFS.md`).

## Build and run (H12)

- **Build** (needs the libraries below first; about a minute, through the lock): `pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: 3d core build" build cmd.exe /c <worktree>\apps\3d\core\build.bat` → `apps\3d\core\.build\install\rostrum3d-core.exe`.
- **Libraries (one folder, outside `proofs\`):** `C:\Users\Sam\.rostrum\libs\3d\5.2.2-cycles-a456b76\` (about 262 MB, about 3,500 files). Make it once with `python -I apps\3d\libs\lay_out.py` — it copies from the proofs' downloads (nothing is downloaded), only what is missing or changed, so a second run takes seconds; `--check` shows what it would copy; it stops loudly if anything is missing. Inside: `runtime\` (the DLLs the engine really loads, Blender's USD resources, Cycles' Hydra plug-in with its GPU kernels, our stylized plug-in), `sdk\` (headers and `.lib` files the core builds against) and `VERSION.json` (which library versions, which commit of our stylized plug-in, date, size). The GPL FFmpeg is never copied. A different folder: set `ROSTRUM3D_LIBS` (run time) or `ROSTRUM3D_SDK` (build).
- **How the engine finds them:** `rostrum3d/runtime.py` puts `runtime\bin` and `runtime\usd\lib` on `PATH` and sets `PXR_PLUGINPATH_NAME` for the child process; a missing folder is a clear error that says to run `lay_out.py`.
- **MCP server:** `python -m rostrum3d.mcp --project <folder> --item <id>` (or the `rostrum-3d` script). Tools: the shared ones plus `look_frame`, `look_sheet`, `look_at`, `render_still`, `render_video`, `inspect_usd_file`, `inspect_shot`. Agents' guide: `python/rostrum3d/guides/agents.md`.

## Layout

| Part | Files |
|---|---|
| Core: requests, Hydra, colour, memory | `core/src/main.cpp`, `serve.*`, `requests.*`, `args.h`, `hydra.*` (one engine per renderer, progressive loop, pick), `gl_context.*` (hidden GL 4.6 context, float framebuffer), `image_out.*` (EXR; OCIO PNG; `.partial` then rename), `gpu_mem.*` (DXGI + NVML), `inspect.*` |
| Core: live viewport | `view_camera.*` (scene or free camera → frustum), `studio.*` (the viewport's studio dome), `outline.*` (selection ring), `shm.*` (pictures in shared memory) |
| Core: scene → USD | `core/src/stage_build.*`, `stage_items.*`, `item_track.h` (per-frame samples), `primitives.*`, `materials.*`, `lights_cameras.cpp`, `json_read.h` |
| Python | `python/rostrum3d/`: `fields.py` (the one table), `kind.py`, `ops_*.py`, `build.py`, `aim.py`, `script.py`, `compile.py`, `engine.py`, `mcp/` |

## Open

- Storm has no depth of field and no soft shadows from the studio light; Cycles has both (side by side: `C:\Users\Sam\.rostrum\waves\results\stage2\3d-screen\storm-vs-cycles.png`).
- The viewport never shows its studio light. A scene with its own dome light is lit by that dome in the viewport and the dome is seen behind the scene, matching Cycles in colour and brightness (H14, H15: `core/src/sky.cpp`). Still open: an HDR dome's horizon sits about 10° lower in Storm than in Cycles (turning the dome changes nothing, so it is the vertical mapping); the newer dome type with its pole axis is untested.
- A viewport picture takes ~60–80 ms at 960×540 (drawing 10–20 ms; the rest is reading back floats and the colour transform on the CPU). Fine for clicking and orbiting, short of 60 fps. Next: the colour transform on the GPU, or the native `QQuickRhiItem` viewport planned in `proofs/gui-qt`.
- The stylized renderer takes no look settings through the contract yet.
- Imports in other units (e.g. centimetres) are not rescaled; the import's scale must be set.

## Python layer (`python/rostrum3d/`, H12)

The document, its operations, the script layer and the compiler to the engine's scene description: see [`DOCUMENT.md`](DOCUMENT.md) and [`ENGINE_CONTRACT.md`](ENGINE_CONTRACT.md). Install: `uv pip install --python <worktree>\.venv\Scripts\python.exe -e apps\3d\python`.

**Done (S11):** the key model's easing table, evaluator and the four key operations (`key.add`, `key.remove`, `value.set`, `key.clear`) live in `rostrum_core.keys`; `rostrum3d` no longer imports `rostrum2d`.

## Attribution rows

Nothing new: the library folder holds the same libraries already recorded in `ATTRIBUTIONS.md` (rows from `proofs/3d-app-start/README.md` and `proofs/3d-product/README.md`): Blender's library bundle `v5.2.2` (commit 60d6e96: OpenUSD, OpenImageIO, OpenColorIO, OpenEXR, Imath, MaterialX, OpenVDB, TBB, Embree, OpenImageDenoise, OpenJPH, libaom, SYCL runtime, epoxy, fmt) and Cycles (commit a456b76). Its GPL FFmpeg is never copied into the folder. Cycles' `license\` folder is copied next to its plug-in (`runtime\hydra\cycles\license`). The Visual C++ runtime DLLs and `python313.dll` (PSF) are copied as fallbacks.
