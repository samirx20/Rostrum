# P-3D-3 · Our own stylized Hydra render delegate ("Rostrum Stylized")

> **Moved (brief 22, 2026-10-27):** the plug-in's source (`src/`, `resources/`, `CMakeLists.txt`, `build.bat`, `LOOKS.md`) now lives in `apps/3d/stylized/` and is built there (`apps/3d/stylized/build.bat` → `apps/3d/stylized/.build/install`). Paths below are the proof's own, kept as the record; `render.py` here finds the plug-in in `apps/3d/stylized/.build/install`.

**Question:** can our own Hydra render delegate (raster, GPU) add what Cycles can't: light-to-colour ramps for every light, ink lines with width and taper, brush-stroke shading, per-shot shape bending; and can renderers be swapped on the same USD stage without changing the scene?

**Verdict: pass with conditions.** Our own Hydra plug-in draws the H2 still-life stage and the H1 product stage on the GPU at about 30 frames a second at 1080p. Storm, Cycles and ours swap by name in one host program, and the scene file never changes. All four look tools work and are driven by data in USD: per-light colour ramps (key, fill, bounce), ink lines with width and taper, brush dabs that break light and shadow edges, and a shape bend that applies to one camera only. The same tools give two clearly different looks. Judged against Fortiche / Mielgo, the frames read as painted, and more so than the Cycles still, but they are **not at that level yet**: the brush dabs are one even screen-space pattern, so they read as a filter and would "swim" in motion, and the light shapes are computed, not designed. Details under "Judged against the quality bar".

## Results (private, not in the repo)

All in `C:\Users\Sam\.rostrum\waves\results\stage1\p-3d-3\`:

| File | What |
|---|---|
| `still-cycles-vs-ours-sidebyside.png` | **the comparison**: H2's Cycles still (real light) · ours, painted look · ours, cel look. Same stage. |
| `still-painted-1080p.png` | ours, painted look layer (ramps on all 3 lights, brush dabs, surface-coloured ink thinning in light, paper grain) |
| `still-cel-1080p.png` | ours, cel look layer (2-step key ramp, flat fill, bounce off, dark even outlines + creases, no brush) |
| `still-no-look-1080p.png` | ours with no look layer (plain lambert per light + default ink) |
| `still-painted-bend-1080p.png`, `still-painted-bend-sidecamera-1080p.png`, `bend-sidebyside.png` | shot layer bends the jug (squash, lean, swell) for `/World/Camera`; the same layers seen from another camera show it unbent |
| `renderer-swap-sidebyside.png`, `still-storm-1080p.png`, `still-cycles-via-host-480p.png` | the same stage through Storm, Cycles and ours, in one host, chosen by name |
| `product-ours-cel-1080p.png`, `product-storm-1080p.png` | H1's product stage through ours and Storm |
| `*.stats.json` | timing, RAM, video memory, look settings per frame |

## Route and why

**Our own `HdRenderDelegate` (Hydra 1 prims) with our own OpenGL raster pass**, built as a plug-in (`hdRostrum.dll`) against the OpenUSD 26.03 in Blender's Windows library bundle (namespace `pxrBlender_v26_03`, `usd_ms.dll`). It is the same bundle H1's Cycles build uses, plus its `epoxy` (MIT) GL loader. It is found by name, `HdRostrumPlugin`, beside `HdStormRendererPlugin` and `HdCyclesPlugin`.

**Why not extend Storm:** Storm's look is set by its own shader and task pipeline (glslfx, HdxTaskController). Ink lines and brush strokes are screen-space passes that need Storm's AOVs and new Hydra tasks, and our app hosts cannot insert those tasks from outside. Ramps per light need Storm's lighting code changed. A small delegate of our own was faster and gives us full control of the frame. Its cost: we write our own mesh, material and light sync (about 1,700 lines, C++ and GLSL together).

**How it draws** (`src/renderPass.cpp`; shaders in `resources/shaders/`, read at run time, so look work needs no rebuild):
1. Shadow maps, one per shadowed light (up to 4, 4096²).
2. A G-buffer at 2× the output size (`rostrum:ss`): albedo, normal + depth, position, object id. The per-camera bend is applied here, and in the shadow pass.
3. Shading. For each light, "how lit" is computed: N·L with wrap and shadow, a hemisphere for dome lights. It is pushed by brush dabs, looked up in that light's colour ramp, then multiplied by the albedo. Emission-only cards (the painted background) are shown exactly as painted.
4. Ink edges: silhouettes, folds and creases get a width, thinned in light and with distance and varied by a slow wobble. An ink pass then draws discs of those widths in a colour taken from the surface.
5. A 2× box filter down to the output, read back into Hydra's colour and depth AOVs. The host composites them like any renderer's.

Everything the GUI could change is data. Light controls are `primvars:rostrum:*` on the UsdLux light. Bend controls are `primvars:rostrum:bend:*` on a mesh. Frame-wide controls are `rostrum:*` renderer settings, which `render.py` reads from a `/RostrumLook` prim in a look layer. A look is a separate USD layer added to the session layer, so the scene file is never touched. **How to use every control: `LOOKS.md`.**

## Build and run

1. Needs H1's bundle (`proofs\3d-product\README.md` steps 1–2) and VS 2022 Build Tools with cmake + ninja.
2. Build (about 1 minute): `pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: hdRostrum build" build cmd.exe /c C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-stylized\build.bat`. Output: `.build\install\` (`hdRostrum.dll` 176 KB, plugInfo, shaders).
3. Python host: `uv venv --python C:\Python313\python.exe .venv-usd` at the worktree root, then `uv pip install --python .venv-usd\Scripts\python.exe PySide6-Essentials PyOpenGL numpy pillow`. The bundle's `pxr` is for Python 3.13.
4. Stages: `python -I proofs\3d-painterly\scene\make_scene.py --out _stilllife.usda`, `python -I proofs\3d-product\scene\make_scene.py`.
5. Render: `pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: H3 render" gpu pwsh -NoProfile -File proofs\3d-stylized\render.ps1 <stage.usda> <out.png> [--renderer rostrum|storm|cycles] [--look looks\painted.usda] [--look looks\shot-bend.usda] [--camera /World/Camera] [--width 1920 --height 1080] [--frames 5]`. `render.ps1` puts the process on the RTX chip (`SHIM_MCCOMPAT`) and records peak video memory. Set `ROSTRUM_SHADERS=<repo>\proofs\3d-stylized\resources\shaders` to try shader edits without rebuilding. Set `ROSTRUM_DEBUG=1` to print each light's controls and the frame time.
6. Side by side: `uv run --with pillow python -I compose.py out.png a.png "A" b.png "B" [--height 540]`.

## Numbers (RTX 3050 Laptop 4 GB, OpenGL 4.6, 1920×1080, 2× supersampling)

| | |
|---|---|
| Frame time, steady (5 frames after the first) | **28–36 ms** (≈ 30 fps), for all looks, incl. Hydra sync, read-back and the host's composite |
| First frame (loading 13 painted 2K textures, compiling shaders) | 0.5 s |
| Video memory, whole GPU peak | **1.18 GB** of 4 (≈ 90 MB before): mostly the 3840×2160 G-buffer and four 4096² shadow maps; `rostrum:ss 1` and `rostrum:shadow:size 2048` cut it to about a quarter |
| RAM (host process peak) | 335 MB |
| Build | about 1 min; `hdRostrum.dll` 176 KB; nothing new downloaded |
| Cycles, same stage, same host (default CPU device) | 255 s at 854×480 (H2's own 1080p GPU still took 38 s) |

## What was checked

- **Renderer swap:** one host, `render.py --renderer`, on the unchanged stage. Storm, Cycles and ours all draw the H2 stage. Ours and Storm also draw H1's product stage.
- **Ramps per light:** the debug log shows each light's ramp, gain and shadow switch arriving from the look layer (`ramp=4 gain=0.75` …). The two looks differ only by their look layer.
- **Bend for one camera:** the bend layer bends the jug and its handle around one shared pivot when `/World/Camera` renders. From `/World/SideCamera`, with the same layers, the jug stands straight.
- **Fails loudly:** a shader that does not compile, a missing shader file, a missing look layer or camera, or any USD/Hydra error makes `render.py` exit non-zero, and the PNG is not written.

## Findings

1. **Custom light inputs don't reach Hydra.** `inputs:rostrum:*` on a UsdLux light is dropped by UsdImaging 26.03, which passes only the light's known inputs. **Constant primvars on the light do arrive** (`primvars:rostrum:*`), so ramps are authored that way. For Rostrum3D: keep primvars, or register a proper `RostrumLightAPI` schema.
2. **The host must clear its framebuffer, depth included, before Hydra renders.** Hydra composites with a depth test. Our first frames were empty, Storm's too, until `render.py` cleared depth to 1. Team Sam's Qt viewport gets this from Qt Quick; the C++ viewport must do it too.
3. **Physical light intensity is ignored by design.** Brightness comes from the ramp × `rostrum:gain`. So a stage lit for Cycles (H1's 8 studio lights) blows out to white without a look layer of its own (`product-ours-cel-1080p.png`). In the app, a stylized look layer is made per scene, or we add an "exposure from intensity" switch.
4. **Cycles in our host crashes on shutdown** (access violation after the frame is saved). It also renders unmanaged colour unless `OCIO` is set, as H2's script did. The frame is right; teardown order between Cycles' session and the GL context needs a look in the C++ viewport.
5. **Brush dabs are screen-space.** They are fixed to the screen, not the surface, so in motion the paint pattern would slide over objects. Dabs that follow the form (`rostrum:brush:follow`) swirl into wood-grain patterns on round objects. The fix for Stage 2 is strokes anchored to the surface (UV or object space) and aligned with a smoothed direction field, plus scale tied to object size on screen.
6. **Limits of the spike:** 8 lights, 4 with shadows. Rect and disk lights are treated as one-sided point lights. No transparency or refraction (the product's glass is opaque). 8-bit textures only. Render tags (proxy / guide) are not filtered. Bend shading uses the unbent normals. Large ink widths are clipped (search radius capped at 12 supersampled pixels).

## Judged against the quality bar (Arcane / Fortiche; Mielgo's The Witness, Jibaro)

What holds up:
- The painted look reads as painted, more than H2's Cycles still. Light falls in graphic shapes (the window pool, the bowl's shadow on the cloth). Shadow edges break into dabs on the table and cloth. Fill and bounce are coloured ramps of their own. Lines are surface-coloured and disappear in light.
- The cel look is clean and readable, with even outlines and hard two-tone light. The same scene and the same tools give a clearly different look.
- It is fast: 30 fps at 1080p. A painter or an agent can turn a control and see the frame, which is the painter's "see it on the model" view H2 asked for.

What does not reach the bar:
1. **The brushwork is a pattern, not painting.** One stroke size and angle across the frame reads as a filter; on the bowl it looks like rain. Fortiche's paint varies by object and plane, and it is placed.
2. **Light shapes are computed, not designed.** In Arcane, light and shadow shapes are art-directed per shot. The tools need editable shadow and light shapes: shadow tweaks, light blockers and gobos per shot, painted light masks.
3. **Forms and drawing:** lathe props and textures from H2 still limit it. The pears still read partly as striped melons.
4. Cel: creases fire rarely on smooth meshes. There is no flat-colour mode for painted textures yet (a texture-simplify control would do it).

**Pass with conditions:** a delegate of our own is the right route for Rostrum3D's stylized look. It has full control, real-time speed, and it is data-driven and swappable with Cycles on one stage. Condition: before judging the look again, add surface-anchored brush strokes and per-shot editable light and shadow shapes.

## What Stage 2's Rostrum3D needs from this

- **Port the pass to Hgi** (OpenGL now, Vulkan/Metal for the Mac) instead of raw GL on the host's context. Then it runs inside Team Sam's C++ `QQuickRhiItem` viewport, and preview ≡ export holds.
- **A `RostrumLightAPI` / `RostrumLookAPI` USD schema** for ramps, gain, wrap, the brush/ink/paper controls and bend, so the GUI and agents edit typed attributes through operations. The `/RostrumLook` prim becomes a `RenderSettings` prim, read through Hydra's render-settings prim (namespace `rostrum`).
- **Surface-anchored strokes** (finding 5) and **per-shot light/shadow shape tools** (judgement 2): the next proof-sized step on the look.
- **Ramps as an editor widget**: a gradient with hard/soft stops, per light. The data is already the ramp's positions and colours.
- Material ramps (a per-material override of a light's ramp), and texture simplify for flat cel colour.
- From H2: tangents for normal maps, and one view transform (OCIO) shared by Cycles and ours. Ours keeps painted cards exactly as painted; Cycles needs the same option.

## Attribution rows

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| libepoxy | from Blender lib-windows_x64 (already downloaded in H1) | MIT | `proofs/3d-stylized` (hdRostrum.dll, OpenGL loading) | dynamic (`epoxy-0.dll`) | yes, with Rostrum3D | Keep the MIT notice | https://github.com/anholt/libepoxy |
| OpenUSD (Hd, Hio, UsdLux) | 26.03, Blender build | Modified Apache 2.0 (TOST) | `proofs/3d-stylized` (delegate base classes, image reading, blackbody colour) | dynamic (`usd_ms.dll`) | yes, with Rostrum3D | Keep the licence and NOTICE; already recorded for P-3D-1 | https://github.com/PixarAnimationStudios/OpenUSD |
| PySide6-Essentials | 6.12.0 | LGPL-3.0 | `proofs/3d-stylized/render.py` (offscreen GL context) | dynamic | dev only | As for PySide6 above | https://pypi.org/project/PySide6-Essentials/ |
