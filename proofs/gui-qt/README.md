# P-GUI · Qt shell proof (parts 1 and 2)

**Status:** part 1 done, 2026-10-21 (Team Sam, brief S1); vsync check and part 2 (USD's Hydra viewport in the window) done in S2. Verdict: **pass with conditions** (below).

## The question

Can Qt (Qt Quick, LGPL, dynamically linked, no GPL-only add-ons), driven from Python, look as Figma-simple as Sam wants **and** hold a live native GPU viewport and smooth 1080p video at full speed in one window? (docs/PROOFS.md › P-GUI)

## What is built

One window, in the dark clean look of the archive design (experiment-final `docs/GUI_DESIGN.md` §9 and the colours, type and spacing in `src/app/ui/kit/tokens.ts`):

- **Top bar:** wordmark, the open document's tab, and a "Search or run a command · Ctrl K" button.
- **Project panel (left):** six items (edit, Motion piece, 3D scenes, sound, comp). Click or ↑ ↓ selects.
- **Viewer (centre):** a **Viewport | Video** switch. Viewport = a live OpenGL scene (a lit, turning torus knot on a soft gradient, 4× anti-aliased) drawn by our own GL code. Video = a 1080p60 H.264 clip through QtMultimedia. A small frame-rate readout (window fps, video fps, memory) toggles with the **FPS** button or **F**.
- **Inspector (right):** the selected item's details; **Tint** swatches and a **Turn speed** slider change the live viewport.
- **Timeline (bottom):** ruler, three tracks, the playhead, play/pause, timecode. Click or drag to scrub.
- **Command bar (Ctrl+K):** a floating list that filters as you type; ↑ ↓ Enter runs, Esc closes. Commands: show viewport, show video, play/pause, go to start, show/hide frame rate, select next/previous item, reset turn speed.
- **Keys:** Space play/pause, Home go to start, ↑ ↓ select, F frame rate, Ctrl+K command bar.

Look tokens live in one file, `qml/Theme.qml`: panels `#1c1c1c` on `#141414`, raised `#262626`, text `#ececec / #a3a3a3 / #929292`, one accent `#4c8dff`; 4 px grid, 8 px gaps between panels, 12 px panel padding, 28 px rows, 32 px panel headers, 6/8 px corners. Panels are separated by background steps, not lines.

**Font:** *Segoe UI Variable Text* (ships with Windows 11), falling back to Segoe UI; numbers in *Cascadia Mono* (ships with Windows 11). On Mac the same list falls back to SF Pro Text / SF Mono. Picked at start in `main.py` (`UI_FONTS`).

## How to run

Python: the team venv, `C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\.venv\Scripts\python.exe` (Python 3.12, PySide6 6.12.0, PyOpenGL, numpy). From `C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\proofs\gui-qt\`:

```
python main.py                                   # opens on the viewport
python main.py --mode video                      # opens on the video
python main.py --measure 20 --mode viewport --out C:\...\viewport.json            # record, write JSON, quit
python main.py --measure 20 --mode video --churn --out C:\...\video-churn.json    # + click around and resize
python main.py --screenshot C:\...\shot.png --mode viewport [--size 1600x960] [--open-commands]  # grab after 2 s, quit
python check_input.py                            # drives keys and clicks, prints what changed
```

- `--video <mp4>` picks the clip (default `C:\Users\Sam\.rostrum\waves\scratch\sam-S1\test_1080p60.mp4`). The test clip was made with: `ffmpeg -f lavfi -i "gradients=s=1920x1080:r=60:d=20:speed=0.015:c0=0x1d2b53:c1=0x7e2553:c2=0x0b6e4f:nb_colors=3" -f lavfi -i "testsrc2=s=480x270:r=60:d=20" -filter_complex "[0][1]overlay=(W-w)/2:(H-h)/2,format=yuv420p" -c:v libx264 -preset veryfast -crf 20 -t 20 test_1080p60.mp4` (1920×1080, 60 fps, H.264 High, 20 s, 7 MB). It lives in scratch, not the repo.
- `--churn`: every 250 ms "clicks" the next project item; every 1.5 s resizes the window (1600×960, 1280×800, 1920×1080, 1440×900; the 1080p screen clamps the big ones).
- `--threaded`: Qt's threaded render loop (see Threading below). `--vsync`: swap interval 1 (see GPU and vsync below). `--on-top`: keep the window above others.
- **Measurement JSON:** window frames and fps; frame-to-frame times (p50, p95, p99, max) from `QQuickWindow.frameSwapped`; frames over 33 ms and 50 ms; decoded video frames and video fps (`QVideoSink.videoFrameChanged`); process memory (working set start / peak / end, private bytes; Windows `GetProcessMemoryInfo` via ctypes, no extra package); the GL vendor / renderer / version. It warms up 1.5 s first. A run with zero frames exits 2; any measure or screenshot run that hangs past its time + 15 s exits 4 with `TIMEOUT`.

## How the viewport is drawn

`viewport.py` · `GLViewport` is a `QQuickFramebufferObject` (registered to QML as `Rostrum.GLViewport`); the window is forced onto the OpenGL backend (`QQuickWindow.setGraphicsApi(OpenGL)`). Each frame Qt calls the renderer's `synchronize()` (GUI thread paused; copies time and tint across) and `render()` with Qt's own GL context current and the item's framebuffer bound. `render()` draws into **our own 4× multisample colour + depth framebuffer** (raw GL via PyOpenGL), resolves it into Qt's framebuffer with `glBlitFramebuffer`, and resets Qt's GL state (`QQuickOpenGLUtils.resetOpenGLState()`). Qt then composites that texture with the rest of the QML screen in the same frame, so panels, popups and the readout draw over it normally.

Why our own framebuffer: overriding `createFramebufferObject()` from Python double-frees the framebuffer object in PySide 6.12 (heap-corruption crash at start). Owning a raw GL framebuffer and blitting is also exactly the shape Hydra wants (below).

`QQuickRhiItem` exists in PySide 6.12 too, but the Python bindings for QRhi command buffers are thin; the FBO item with raw GL is the path usdview-style code already follows. The C++ apps should use `QQuickRhiItem` (next section).

## Hydra plug-in plan (how USD's viewport drops into the same spot)

**How usdview does it:** `StageView` is a `QOpenGLWidget`. In `paintGL()` it sets the camera framing and render-buffer size on a `UsdImagingGLEngine` (Python `pxr.UsdImagingGL.Engine`), sets lighting and selection, then calls `engine.Render(rootPrim, renderParams)`. Hydra Storm draws through **Hgi** (on Windows/Linux `HgiGL`) into its own render-buffer textures (colour, depth), and **HgiInterop** composites the colour (and depth) result into whatever GL framebuffer is bound, which is the widget's.

**In our Qt Quick window it takes the `GLViewport` slot:**

1. Create the `UsdImagingGLEngine` lazily inside the first `render()` call, where Qt's GL context is current (Hydra needs a current context to create `HgiGL`). Destroy it on the render thread when the item goes away.
2. `synchronize()` (GUI thread paused) copies what the GUI owns: camera, current time code, selection, display settings, viewport size.
3. `render()` sets framing to the item's framebuffer size and calls `engine.Render(...)`. HgiInterop writes into the bound framebuffer, the same place our blit writes today. Then `resetOpenGLState()`.
4. In the C++ apps (Rostrum3D, Editor) this is a `QQuickRhiItem` subclass in C++: with the OpenGL backend, wrap the item's colour texture (`QRhiTexture::nativeTexture()`) in a GL framebuffer and let HgiInterop composite into it. Being native code, it never takes the Python lock, so Qt's threaded render loop is fine.
5. **Open design point for P-3D-1:** Hydra reads the USD stage during `Render()`. With Qt's threaded loop that runs while the GUI thread may edit the stage. Either edits go through a queue applied in `synchronize()`, or the 3D viewport renders on the one-thread loop (as usdview's `QOpenGLWidget` effectively does).

**Vulkan / Metal later:** Hgi has `HgiMetal` (macOS, where OpenGL is deprecated and stuck at 4.1) and `HgiVulkan` (experimental). Qt Quick's RHI runs on Metal / Vulkan / D3D too. The plug-in spot stays the same `QQuickRhiItem`; only the backend changes: Hydra renders into a native `MTLTexture` / `VkImage` that Qt wraps with `QRhiTexture::createFrom()`, with no GL in between. On the Mac this is the path to take; GL-only is a Windows/Linux shortcut.

## Video backend and licence

QtMultimedia (`MediaPlayer` + `VideoOutput`), **FFmpeg backend** (Qt 6's default on Windows; `QT_MEDIA_BACKEND=ffmpeg` is set for the record). The PySide6 6.12.0 wheel ships the FFmpeg libraries as separate DLLs (`avcodec-63.dll`, `avformat-63.dll`, `avutil-61.dll`, `swscale-10.dll`, plugin `ffmpegmediaplugin.dll`), i.e. dynamically linked. Qt Multimedia and PySide6 are **LGPL-3.0**; Qt's bundled FFmpeg is an **LGPL** build. All dynamic, so this fits the licence rule. (The test clip was encoded with the system ffmpeg's libx264, which is GPL, but only to make a scratch file; nothing of it ships.)

## Verdict (early, lead, 2026-10-21)

**Pass with conditions.** On this laptop, one Qt Quick window driven from Python holds a live GPU viewport (~125 fps, no hitches while clicking around and resizing) and a 1080p60 video that decodes and shows at a steady 60 fps, next to panels that look calm and uncrowded. The look is the experiment's design carried over almost one-to-one; nothing in Qt fought it. Conditions:

1. ~~Screen-synced drawing (vsync) still has to be checked.~~ **Cleared in S2** (see "Vsync, settled" below): with the screen awake, vsync on holds a locked 60 fps on both chips, viewport and video. The 4–6 fps seen in S1 is Windows holding back drawing while the screen is off.
2. **The real viewport is native code.** Drawing GL in Python works but forces Qt's one-thread mode (see Threading). Real apps draw in Rust / C++ (`QQuickRhiItem`), which the Hydra plan below follows. **S2:** USD's Hydra (Storm, and Cycles as a bonus) now draws in the same slot, still through Python, at ~120 fps uncapped and a locked 60 with vsync (see "Part 2" below).
3. **The app must ask Windows for the fast graphics chip** (`NvOptimusEnablement` export in our own `.exe`); Python runs on the AMD built-in chip by default.
4. **Mac not run yet.**

Is Qt simple enough to look the way Sam wants? From these screenshots, yes: generous spacing, one accent colour, sharp type, panels set apart by shade rather than lines. Sam judges the screenshots below.

## Vsync, settled (S2, 2026-10-21)

The laptop had had no keyboard or mouse input for ~40 minutes and Windows turns the screen off after 5 minutes (Balanced plan, on mains), so before each run a small script (`C:\Users\Sam\.rostrum\waves\scratch\sam-S2-lead\vsync_run.py`, deleted after) woke the screen with a 0-pixel mouse nudge, asked Windows to keep the display on (`SetThreadExecutionState`), and recorded how long the machine had been idle. One run was made first with the screen left as it was, as the control.

| Run (vsync on, 15 s, 1600×960) | GPU | Screen | Window fps | Frame ms p50 / p95 / p99 / max | > 33 ms | Video fps | Memory MB start / peak / end |
|---|---|---|---|---|---|---|---|
| viewport (control, 12 s) | AMD built-in | off (idle 40 min) | **3.8** | 262 / 271 / 453 / 453 | all | — | 270 / 270 / 270 |
| viewport churn | AMD built-in | woken | **60.0** | 16.7 / 17.4 / 23.6 / 27 | 0 | — | 269 / 269 / 266 |
| video churn | AMD built-in | woken | 55 | 16.7 / 32.3 / 40.3 / 63 | 10 of 826 | **60.1** | 382 / 711 / 525 |
| viewport churn | RTX 3050 | woken | **59.7** | 16.6 / 18.4 / 25.7 / 112 | 4 of 896 | — | 341 / 344 / 329 |
| video churn | RTX 3050 | woken | **59.8** | 16.7 / 20.0 / 28.4 / 79 | 3 of 897 | **60.0** | 365 / 370 / 355 |

JSON: `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\measure-vsync-*.json` (each has a `screen` block: woken or as-is, idle seconds before).

Reading it: the same command gives 3.8 fps with the screen off and a locked 60 fps the moment the screen is on, so the S1 crawl was the dark screen, not Qt or the drivers. With vsync on, frames land on the display's 60 Hz beat (p50 16.7 ms), the few slow frames come with the window resizes in churn, and video is shown frame for frame. The built-in chip shows 10 late frames out of 826 in video churn (resizing a playing 1080p video window); the RTX is steadier.

**What it means for the apps:** draw with vsync on (it also stops the wasted ~125 fps of the vsync-off runs). Never time anything by the window: exports and agent frame grabs render offscreen, so a sleeping screen can't slow them (preview ≡ export still holds: same render path, only the presentation differs). Caveat: the screen was woken by a script, not by Sam at the keyboard; the numbers are what a watched screen gets.

## Part 2 · USD's Hydra viewport in the window (S2, 2026-10-21)

**Verdict: pass with conditions.** USD's own viewport engine (Hydra Storm) draws a real USD stage, Team Hem's product scene, live inside our Qt window, in the same spot as the test viewport, with orbit, pan, zoom and click-to-pick by mouse. It holds ~120 fps uncapped and a locked 60 fps with vsync on both chips while the camera turns every frame, picks run, the selection changes 4× a second and the window resizes, using ~470–660 MB. The same viewport switches to Cycles (Hem's Hydra plug-in) and refines a path-traced picture in the window. Conditions: Storm's default look needs work (Findings); the real app does this in C++, not Python; Mac not run.

**Route.** Blender's Windows library bundle that Team Hem downloaded for Cycles (`C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-product\.build\cycles\lib\windows_x64\`) has OpenUSD (namespace `pxrBlender_v26_03`, one DLL `usd_ms.dll`) **with Python 3.13 bindings** (`usd\lib\python\pxr`, incl. `UsdImagingGL`). So no native helper and no build were needed: a second venv of our own, `C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\.venv-usd\` (Python 3.13.4 from `C:\Python313`, PySide6 6.12.0, PyOpenGL, numpy, pefile), imports `pxr` straight from the bundle. Read-only: `hydra_viewport.load_usd()` adds the bundle's DLL folders to the DLL search **and** to `PATH` (USD loads Hydra plug-ins with plain `LoadLibrary`, which ignores Python's DLL folders), skips the bundle's own Python and its GPL FFmpeg, and turns off `.pyc` writing.

**How it is built** (`hydra_viewport.py`, ~240 lines). `HydraViewport` is a `QQuickFramebufferObject` with the same `time` / `tint` properties as `GLViewport`, registered under the same QML name, so `Viewer.qml` didn't change (only the readout now shows the picked prim). It follows the plug-in plan above:
1. The renderer creates `UsdImagingGL.Engine()` in the first `render()`, on Qt's current GL context (Hgi = HgiGL).
2. `synchronize()` hands over the GUI's pending camera operations (orbit / pan / zoom / home / pick) and the time, and hands back the picked prim path. Mouse events never touch the engine; they queue operations, the operation-first shape the apps need.
3. `render()` applies the operations to a turntable camera (it starts from the stage's first camera: position, aim, focus distance, field of view), sets render-buffer size, framing and camera, and calls `engine.Render()`; HgiInterop composites into the framebuffer Qt bound. Picking is `engine.TestIntersection()` through a 4-pixel frustum around the click (usdview's way).
4. A failure inside `render()` prints the error and exits with code 3 (fail loudly, no blank viewport).

Mouse: left drag orbit, middle drag or Shift + left drag pan, wheel or right drag zoom, click pick, double-click home. The Turn speed slider turns the view slowly (off for progressive renderers, which restart on every camera move).

**Run** (from `C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\proofs\gui-qt\`):
```
C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\.venv-usd\Scripts\python.exe main.py --stage ..\3d-product\scene\product.usda
   [--hydra-lights camera|scene]   camera = a head light (default); scene = the stage's own lights
   [--hydra-renderer HdCyclesPlugin --hydra-plugins C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-product\.build\cycles\install\hydra]
   [--measure 15 --churn --out x.json] [--screenshot x.png --shot-delay 25] [--usd-bundle <folder>]
```
The stage comes from Hem's script: `python -I ..\3d-product\scene\make_scene.py` writes the ignored `product.usda` (51 prims, 2 MB). With `--stage`, `--measure --churn` also orbits and picks through the same operations the mouse uses; the JSON lists the prims it picked.

**Measurements** (15 s, 1600×960 window, screen woken as in "Vsync, settled"; churn = camera turning every frame + an orbit step every 250 ms + a pick every second + project selection every 250 ms + a resize every 1.5 s):

| Run | GPU | Window fps | Frame ms p50 / p95 / p99 / max | > 33 ms | Memory MB start / peak / end | Picked |
|---|---|---|---|---|---|---|
| Storm, vsync off | AMD built-in | **122** | 6.6 / 13.5 / 18.3 / 191 | 3 of 1831 | 530 / 661 / 657 | (pick result misread; fixed before the RTX runs) |
| Storm, vsync on | AMD built-in | **58.6** | 16.7 / 17.4 / 32.6 / 99 | 8 of 879 | 521 / 643 / 643 | (same) |
| Storm, vsync off | RTX 3050 | **119** | 5.7 / 14.9 / 18.8 / 461 | 4 of 1777 | 462 / 537 / 522 | TopGlass, Dial/Lens, Dial/DialKnurl |
| Storm, vsync on | RTX 3050 | **59.8** | 16.7 / 19.5 / 27.8 / 84 | 8 of 897 | 467 / 476 / 461 | TopGlass, Dial/Lens, Dial/DialBezel |

JSON: `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\measure-hydra-*.json`. The slow frames come at the first frame and at window resizes (Hydra reallocates its render buffers), not while orbiting. The RTX runs used the same temporary per-program GPU setting as S1, for `C:\Python313\python.exe` and the venv's python, removed right after.

**Screenshots** (RTX 3050):
- `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\window-hydra.png`: Storm with the head light. Plain but readable.
- `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\window-hydra-scene-lights.png`: Storm with the stage's own studio lights: blown out.
- `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\window-hydra-cycles.png`: bonus, the same viewport on **Cycles** (`HdCyclesPlugin`), 25 s into a progressive render with the scene's lights. Grainy (default device, no denoiser), but it is the real product shot refining inside our window. Compare Hem's finished still `C:\Users\Sam\.rostrum\waves\results\stage1\p-3d-1\product-still-1080p.png`.

**Findings:**
- **Storm's out-of-the-box look is not good enough for a product scene.** With the scene's lights, Storm treats the big soft studio lights (rect lights tuned for Cycles) as bright small lights and the picture blows out. With a head light, metal looks black and the glass top hides the dial, because Storm has no environment to reflect. Fix in the real app: a default studio environment (dome light with an HDR image) and an exposure control in the viewport, as usdview and Blender's viewport have. These are viewport settings, not a new route.
- **Cycles in the viewport works as is.** A 3D viewport can offer "fast (Storm) / final (Cycles)" as one switch. To be usable live, Cycles needs the GPU device (OptiX) and the denoiser on; not tried (time box).
- **The bundle's USD is a Blender build** (`pxrBlender_v26_03` namespace, one big `usd_ms.dll`). Fine for a proof; the app should ship its own OpenUSD build (or vcpkg's) so we choose the version and plug-ins.
- **Python on the render thread again.** Same limit as part 1: this viewport is driven from Python, so it runs on Qt's one-thread loop. In Rostrum3D it is the C++ `QQuickRhiItem` from the plan; `hydra_viewport.py` is a 1:1 sketch of it (engine calls, operation queue, framing, picking).
- **Read-only use of Hem's build:** my first import, before `.pyc` writing was off, left three `__pycache__` folders in Hem's bundle (`…\windows_x64\usd\lib\python\pxr\__pycache__`, `…\pxr\Tf\__pycache__`, `…\pxr\Usd\__pycache__`, made 2026-10-21 16:09). Harmless bytecode caches; deleting inside Hem's worktree is not ours to do, so they are left for Team Hem.

## Results

Screenshots for Sam (RTX 3050, 1600×960 window at this screen's 125 % scaling):

- `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\window-viewport.png`: the live 3D viewport
- `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\window-video.png`: the 1080p video playing
- `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\window-command-bar.png`: Ctrl+K command bar open
- `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\window-small-1280x800.png`: a smaller window

Measurements: 20 s each, one-thread render loop, vsync off, at 1600×960. `churn` = "clicks" the next project item every 250 ms and resizes the window every 1.5 s. Memory is the process working set; JSON files in `C:\Users\Sam\.rostrum\waves\results\stage1\p-gui\measure-*.json`.

| Run | GPU | Window fps | Frame ms p50 / p95 / p99 / max | > 33 ms | Video fps | Memory MB start / peak / end |
|---|---|---|---|---|---|---|
| viewport | AMD built-in | 125 | 6.0 / 12.5 / 13.2 / 16 | 0 | — | 266 / 266 / 263 |
| viewport churn | AMD built-in | 125 | 5.7 / 12.6 / 16.7 / 32 | 0 | — | 267 / 267 / 265 |
| video | AMD built-in | 60 | 16.5 / 20.6 / 23.7 / 51 | 10 of 1210 | **60.0** | 379 / 613 / 612 |
| video churn | AMD built-in | 63 | 16.5 / 19.1 / 36.5 / 50 | 16 of 1263 | **60.0** | 373 / 727 / 643 |
| viewport | RTX 3050 | 125 | 6.0 / 12.7 / 13.4 / 74 | 1 | — | 394 / 395 / 394 |
| viewport churn | RTX 3050 | 126 | 5.5 / 12.8 / 15.6 / 76 | 1 | — | 343 / 346 / 330 |
| video | RTX 3050 | 60 | 16.7 / 18.3 / 20.6 / 114 | 7 of 1191 | **60.0** | 422 / 424 / 424 |
| video churn | RTX 3050 | 82 | 11.1 / 18.2 / 20.4 / 161 | 3 of 1632 | **60.0** | 364 / 369 / 356 |
| viewport churn, vsync | RTX 3050 | 6 | 254 / 266 / 273 / 346 | all | — | 332 / 338 / 317 |
| video churn, vsync | RTX 3050 | 6 | 236 / 275 / 286 / 333 | all | 60.0 | 355 / 364 / 363 |

Reading it: the viewport never dropped under 60 fps; ~125 fps is Qt's own pacing cap with vsync off. Video was decoded and shown at a steady 60 fps in every run; the window drew a frame for each. The few slow frames (one per run on the RTX, 74–161 ms) happen at a window resize or at start, not during playback. Memory stays under ~730 MB with video, ~400 MB without. The vsync rows are the unattended-screen problem in the verdict, not a real speed.

How these were run (lead, through `heavy.ps1` gpu slots): `python main.py --measure 20 --mode viewport|video [--churn] [--vsync] --out <json>`. The RTX runs used a temporary per-program Windows graphics setting (`HKCU\Software\Microsoft\DirectX\UserGpuPreferences`, `GpuPreference=2`) for the venv's python, removed right after.

## Findings

- **GPU and vsync.** By default Windows runs `python.exe` on the **AMD Radeon iGPU**, not the RTX 3050 (the JSON's `gl` block shows it). With vsync on (swap interval 1), *any* Qt Quick GL window, even a bare spinning rectangle, ran at **~4–6 fps** on both chips, even with `--on-top`; most likely because nobody was at the laptop and the screen was off (see Verdict). With swap interval 0, Qt paces frames itself and Windows' compositor still prevents tearing, so that is the default here (`--vsync` to compare). To test on the RTX 3050: Windows Settings › Display › Graphics › add `C:\Users\Sam\AppData\Roaming\uv\python\cpython-3.12.11-windows-x86_64-none\python.exe` › High performance. A shipped app's own `.exe` would ask for the fast GPU itself (`NvOptimusEnablement` / `AmdPowerXpressRequestHighPerformance` exports).
- **Threading.** Our viewport draws in Python, so Qt's render thread needs Python's lock. Any GUI-thread Python call that waits for the render thread (`win.resize()`, `grabWindow()`, `QTest.qWait`) then deadlocks; it happened at random at start-up. The proof therefore uses Qt's **one-thread render loop** by default (`--threaded` to try the other). Screenshots use `grabWindow()` on that loop (whole window, popups included); with `--threaded` they fall back to QML's async `grabToImage` of the panels (no popups). This is a limit of drawing GL *in Python*, not of Qt: the real viewports are native code (Rust / C++) and won't take the Python lock. Rule for the real apps: **Python never draws on the render thread.**
- **Command bar** has no drop shadow yet (the archive tokens give popovers one); it reads fine over the dark viewport. A GUI-kit polish item.
- **Uncapped viewport.** Without vsync the one-thread loop draws the viewport as fast as it can (~125 fps here). Smooth, but wasted GPU work; a real app caps to the display rate.
- **Video memory.** Video mode's working set climbs to ~700 MB during resizes (FFmpeg frame pools), then settles. Watch it in the 20 s runs.
- **Mac:** not run. Expected: Qt Quick on Metal; this GL proof runs there on GL 4.1 (the shaders are GLSL 330), but the real viewport should go through RHI / Metal (Hydra plan above).

## What's left

- Mac run.
- Hydra: studio environment + exposure for Storm; Cycles on the GPU with the denoiser in the viewport; the C++ `QQuickRhiItem` version (Rostrum3D).
- Command bar drop shadow; playhead line stops at the last track.
- Not built: real panel resizing (splitters), tabs for several documents, hover tooltips, light theme. Icons are letters in chips; a real icon set is a GUI-kit job.
- HiDPI: with this screen's display scaling a 1600×906 window grabs at 1867×1057 pixels; text stays sharp. (The 1080p screen also clamps a 960 px-tall window to 906.)

## Files

`main.py` (start-up, flags), `viewport.py` (the GL viewport), `hydra_viewport.py` (USD's Hydra in the same slot), `measure.py` (readout, memory, measure and screenshot drivers), `check_input.py` (keys and clicks check), `qml/` (`Main.qml` state and commands, `Theme.qml` look tokens, `TopBar`, `Panel`, `ProjectPanel`, `Viewer`, `Inspector`, `Timeline`, `CommandBar`).
