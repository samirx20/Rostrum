# P-GUI · Qt shell proof (part 1)

**Status:** part 1 done, 2026-10-21 (Team Sam, brief S1). Verdict: **pass with conditions** (below).

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

1. **Screen-synced drawing (vsync) still has to be checked with Sam at the laptop.** With vsync on, every run (both graphics chips, window on top or not) crawled at ~6 fps. The runs were unattended with the laptop idle for 35 minutes, so the screen was most likely off, and Windows holds back screen-synced drawing then. The proof's default (vsync off, Qt paces frames) is smooth. One attended run settles it: `python main.py --vsync` and watch the FPS readout.
2. **The real viewport is native code.** Drawing GL in Python works but forces Qt's one-thread mode (see Threading). Real apps draw in Rust / C++ (`QQuickRhiItem`), which the Hydra plan below follows.
3. **The app must ask Windows for the fast graphics chip** (`NvOptimusEnablement` export in our own `.exe`); Python runs on the AMD built-in chip by default.
4. **Mac not run yet.**

Is Qt simple enough to look the way Sam wants? From these screenshots, yes: generous spacing, one accent colour, sharp type, panels set apart by shade rather than lines. Sam judges the screenshots below.

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

- One attended run with vsync on (`python main.py --vsync`, read the FPS readout) to clear condition 1.
- Mac run.
- Command bar drop shadow; playhead line stops at the last track.
- Not built: real panel resizing (splitters), tabs for several documents, hover tooltips, light theme. Icons are letters in chips; a real icon set is a GUI-kit job.
- HiDPI: with this screen's display scaling a 1600×906 window grabs at 1867×1057 pixels; text stays sharp. (The 1080p screen also clamps a 960 px-tall window to 906.)

## Files

`main.py` (start-up, flags), `viewport.py` (the GL viewport), `measure.py` (readout, memory, measure and screenshot drivers), `check_input.py` (keys and clicks check), `qml/` (`Main.qml` state and commands, `Theme.qml` look tokens, `TopBar`, `Panel`, `ProjectPanel`, `Viewer`, `Inspector`, `Timeline`, `CommandBar`).
