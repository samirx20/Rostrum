# P-3D-viewport proof: the 3D viewport drawn inside the window's own process

*Team Priyam, 2026-10-27, brief `3d-pview-inprocess-r1`. Throwaway proof code: nothing here goes into `apps\` or
`shared\` (the clay files are compiled straight from `apps\3d\core\src`, unchanged). Pictures and numbers:
`C:\Users\Sam\.rostrum\waves\results\3d-pview\`.*

## The call: PASS WITH CONDITIONS

**In plain words.** Drawing the 3D view inside the app's own window, instead of in the separate engine program and
sending the picture back, removes the delay the old way could never get under. A brush dab on clay now reaches the
screen in **8 ms** (slowest tenth 9 ms), where the app today takes 92 ms (113 ms). A big brush a quarter of the clay
across takes 10 ms (12 ms). Turning the camera around a 300-object scene takes about 2 ms a frame. All four are well
inside the 16 ms / 25 ms target, and the whole window uses about 0.3 GB of memory.

**The conditions.** On a clay with very fine grain (the scripted head at 0.625 mm, what a close-up shot asks for)
the target is still missed: 24 ms (40 ms) with the medium brush, 58 ms (109 ms) with the quarter brush. Moving the
viewport does not fix that. The time there is the clay's own work and Storm re-loading the changed parts of the
surface, so that is the next job (below). Two smaller conditions: letting go of a stroke freezes the view for 50 to
200 ms while the stroke is applied again as one piece, so that has to move off the drawing thread. And the wait for
the screen's next refresh (0 to 16.7 ms, about 8 ms on average) could not be measured, because the screen was asleep
during the runs. It adds the same amount in the old and the new design.

## What was built

`src/main.cpp`: a C++ Qt Quick window (Qt 6.12, the same version as the apps' PySide6). The window holds a
`HydraView` (`src/view.*`): a `QQuickRhiItem` on the OpenGL backend. Its renderer draws a USD stage with Storm
(`UsdImagingGLEngine`, HgiGL) straight into the item's own colour texture: the texture is wrapped in a GL framebuffer
and Storm's presentation step (HgiInterop) composites into it, inside the window's process, on Qt's render thread.
`src/draw.*` holds the stage, the clay and Storm, with no Qt in it. The clay is the core's own code (`Volume`,
`StrokeDabs`, `Resampler`, `Blocks`: narrow-band volume, 32³ block meshes, one Mesh prim per block, only the changed
blocks re-sent). It is changed in the same process on a left drag, with right drag to orbit. The program runs on the
RTX through the two exported flags. A QML label drawn over the 3D view shows the live numbers.

It drives itself with QTest mouse events at 60 moves a second, like the CL2b hop runs. Four strokes of 50 moves go
across the clay. The orbit run uses one right-drag of 300 moves (600 for the fast run). The window opens in the
background (`ROSTRUM_BACKGROUND_WINDOWS=1`). Each run writes a JSON file (every move's hops), a picture of the window
and a picture of the 3D item. Build: `build.bat`. Run: `run.bat …`. All runs: `runs.ps1`. Each run goes through
`heavy.ps1`.

### The open design point (gui-qt README, Hydra plug-in plan, point 5): settled

**The render thread owns the stage. The GUI thread never touches it.** The GUI thread queues pointer events and the
camera. `synchronize()` (GUI thread paused) moves the queue across. `render()` then applies the queued dabs
(dab -> mesh -> USD), then draws, in that order, on one thread. So Hydra never reads a stage someone else is
editing, there are no locks around USD, and a dab never blocks the GUI thread. The same code also runs on Qt's
one-thread loop (`--loop basic`: 7.1 ms / 9.0 ms), which is what check windows use. So both options in the README
work, and the queue is the one to keep.

**One more thing was needed for speed: draw on input.** `update()` alone waits for Windows' next frame tick, which
follows the display refresh. That wait added ~15 ms to every move (run `sculpt-medium-tick`: 22.7 ms). The item
sends the window an UpdateRequest when a sculpt or orbit move arrives, so the frame syncs at once. The render loop
still waits for the frame before, so frames never pile up.

## Numbers

Laptop RTX 3050 4 GB, 16 GB, window 1493 × 933 px. Swap interval 0 (what check windows use, and what CL2b measured
with), glFinish after Storm (so "on screen" includes the GPU's own work). "Move -> on screen" runs from the moment
the driver sends the mouse event into Qt to the moment `frameSwapped` fires for the frame that shows it. Median /
slowest 10 % (90th percentile), ms. 200 moves per sculpt run; every move carried a dab.

| Run | Move -> on screen | Waiting | Dab | Mesh | USD | Storm + finish | To swap | Peak memory |
|---|---|---|---|---|---|---|---|---|
| **Add, medium brush (12 mm), ball at the app's default 2 mm grain** | **8.1 / 9.3** | 0.7 | 1.4 | 0.9 | 0.6 | 3.7 | 0.8 | 289 MB |
| **Add, quarter brush (37.5 mm), same ball** | **9.8 / 12.4** | 0.5 | 2.2 | 1.3 | 1.1 | 3.9 | 0.7 | 301 MB |
| Add, medium, Qt's one-thread loop | 7.1 / 9.0 | 0.1 | 1.4 | 0.7 | 0.5 | 3.7 | 0.6 | 273 MB |
| Add, medium, waiting for Qt's frame tick (no draw-on-input) | 22.7 / 26.2 | 15.1 | 1.4 | 0.7 | 0.5 | 5.8 | 0.6 | 286 MB |
| Add, medium, **head at 0.625 mm** (598 blocks) | 24.1 / 40.2 | 0.9 (p90 17.6) | 5.1 | 2.1 | 1.5 | 10.7 | 1.2 | 1.21 GB |
| same, without the glFinish | 21.7 / 35.5 | 1.4 | 5.4 | 2.1 | 1.5 | 7.8 | 1.1 | 1.21 GB |
| Add, quarter (41 mm), **head at 0.625 mm** | 57.9 / 108.6 | 0.7 (p90 51) | 12.5 | 6.8 | 5.3 | 25.1 | 1.1 | 1.21 GB |
| Add, medium, vsync on (screen asleep) | 268 / 523 | — | 1.5 | 0.7 | 0.5 | 253 | — | 276 MB |

(Hops are medians. The vsync-on run measured nothing useful: with the display asleep, every frame blocks ~250 ms, the
known Windows behaviour (gui-kit `background()`). It has to be measured again with the screen on.)

**Orbit, 300 objects + the clay ball + a floor** (`orbit-300`, `orbit-300-fast`): a frame takes **2.5 ms** (slowest
10 %: 4.6) at 60 moves a second, and 1.9 ms (2.4) when driven as fast as possible. Move -> on screen is 3.9 / 5.1 ms
(3.0 / 3.9). Peak memory is 279 MB. In a first fast run the picture changed ~418 times a second. In the final run,
Windows' timer (15.6 ms steps) held the driver to 70–100 moves a second; drawing did not hold it back.

**Against the app today (CL2b, the same mouse moves, Add):** 161 -> 92 ms median, 113 slowest 10 %, with a design
floor of ~55 ms. Here the whole trip apart from the work itself costs ~2 ms: delivering the event 0.5–1 ms and
finishing the frame ~1 ms. There is no request queue, pipe, JSON, read-back, picture copy or texture upload. On the
same 2 mm clay that is **8 ms instead of 92**.

**Letting go of a stroke** (the stroke put back and applied as one unit, so the kept clay is exactly the clay seen):
47–86 ms on the ball, 170–600 ms on the head, on the render thread. The view stops for that long once per stroke.

Pictures (each run's folder also has `*-item.png`, Storm's own frame):
- `C:\Users\Sam\.rostrum\waves\results\3d-pview\sculpt-medium\sculpt-add-medium-window.png`, the four medium strokes on the ball
- `C:\Users\Sam\.rostrum\waves\results\3d-pview\sculpt-quarter\sculpt-add-quarter-window.png`, the quarter brush
- `C:\Users\Sam\.rostrum\waves\results\3d-pview\head-medium\sculpt-add-medium-head-window.png`, the head with four strokes across the face
- `C:\Users\Sam\.rostrum\waves\results\3d-pview\orbit-300\orbit-300items-every16ms-window.png`, the 300-object scene

## Found on the way

- **Never name the program `pview.exe`.** The NVIDIA driver (596.36) has an application profile for that file name
  that caps OpenGL at 1.2. Storm then fails ("HgiGL minimum OpenGL requirements not met") and shaders compile without
  a `#version`. A standalone WGL probe gave 4.6 under any other name and 1.2 as `pview.exe`. Rostrum3D's own program
  names should be checked the same way once (`PVIEW_PROBE=1` prints what a context gets).
- **Qt leaves its GL state behind.** Storm drew only its clear colour until the GL state was reset before
  `Render()` (scissor, blend, cull, depth mask/range, colour mask, VAO, program, buffers; `draw.cpp`).
  `beginExternal()`/`endExternal()` only protect Qt from us, not us from Qt.
- **Qt 6.12 moved `qrhi.h`** into the versioned headers: link `Qt6::GuiPrivate` and include `<rhi/qrhi.h>`.
- Qt C++ SDK: Qt 6.12.0 msvc2022_64 (qtbase + qtdeclarative) in `C:\Users\Sam\.rostrum\libs\qt\6.12.0-msvc2022_64`.
  It was fetched by hand from a Qt mirror because aqtinstall does not know the 6.12 repository layout yet. The
  checksums match download.qt.io's.

## Plan: moving Rostrum3D's viewport to this (one page)

**Shape.** The app stays a Python + PySide6 program. The viewport becomes a **C++ QML module** (a `QQuickRhiItem`,
this proof's `HydraView` grown up), built against Qt 6.12 to match PySide6's own Qt DLLs, and loaded by
`app/qml/Viewport.qml` in place of today's `Image { source: "image://view/…" }`. The engine program stays, for
everything that isn't the live view.

**apps\3d\core (C++)**
1. Split the core into a library (`r3d_core`: scene build, Hydra/`hydra.cpp`, view post (OpenColorIO, contact
   shading, depth of field, outline, ghosts, studio dome / sun), pick, the clay store) and two thin programs that
   link it: `rostrum3d-core.exe` (today's JSON server, unchanged contract) and the QML module
   `Rostrum3DView` (`viewport_item.cpp`). The view post code renders into the item's framebuffer instead of a
   read-back. No second copy of any look code: the in-window view must look exactly like the engine's pictures.
2. The item's renderer owns its own stage and clay store on Qt's render thread (the rule above). Requests arrive
   as `Q_INVOKABLE`s from Python: `setScene(json)` (the same scene JSON the engine gets), `setView({...})` (today's
   `view` arguments), `pick(...)`, and the `sculpt` phases. They are queued, moved in `synchronize()` and applied
   in `render()`. Replies (pick hit, sculpt `point`/`normal`, `end`'s dab file name, timing, VRAM) come back as
   queued signals. The contract stays the ENGINE_CONTRACT one, as a second transport.
3. Draw on input: a pointer move sends the window an UpdateRequest (above).
4. Stroke end on a worker: `end_stroke` re-applies the stroke into a copy (or under a short lock) off the render
   thread. The live picture already equals the result, so nothing on screen changes while it runs.
5. Fine-grain clay (the remaining miss), in this order: (a) overlap the dab and mesh for move n+1 with Storm's draw
   of move n (dab and mesh on a worker, the USD write in `render()`); (b) cut Storm's per-dab cost: CL2b counted a
   garbage collection and ~110 GPU buffer copies after every dab, and here Storm's draw grows 3.7 -> 10.7 -> 25 ms
   with the changed surface; (c) only then smaller blocks near the brush. Target: the head with the medium brush at
   or under 16 ms.
6. Build: `apps\3d\core\CMakeLists.txt` gets `find_package(Qt6 Gui GuiPrivate Qml Quick)` against the Qt SDK
   folder (or PySide6's Qt plus its headers). It installs the module's `qmldir` + DLL next to the core, and the
   program keeps a name the NVIDIA driver doesn't trap.

**apps\3d\app (Python + QML)**
1. `Viewport.qml`: the `Image` becomes `Rostrum3DView { }`. The gizmo, brush ring, rails and overlays stay QML
   items on top of it, as today.
2. `screen3d/viewport.py`, `clay_stroke.py`, `focus_pick.py`, `gizmo_drag.py` and the other users of `view` / `pick`
   / `sculpt` keep their logic but call the item, not `engine.py`'s pipe. A small adapter with the engine client's
   method names keeps the change mechanical. The scene compile stays where it is: the same JSON goes to both the item
   and the engine.
3. The picture provider, the shared-memory reader and the "drawn off the GUI thread" picture worker are removed
   from the live view.
4. The **Final look** (progressive Cycles in the viewport) stays in the engine program and still arrives as a
   picture. Speed matters less there, and ending a Hydra Cycles engine inside a running program crashed it
   (ENGINE_CONTRACT § 4), which must not happen inside the window.

**What agents and MCP keep using the engine program for:** Final renders (`render`, Cycles, frame ranges, passes),
headless pictures for look tools and checks (`view` with no window), `pick` without a screen, agent sculpting
(`sculpt` along paths, `clay_info`, `clay_bench`), `inspect_usd`, `unfold`, `save`. All unchanged. The clay's
contract (live = replay = cache, dab files named by content) means the window and the engine program always build
the same clay from the same document.

**Costs to accept.** The window process holds its own stage and clay, next to the engine program's (~0.3 GB at
2 mm, ~1.2 GB for the 0.625 mm head). The engine program can drop its own live clay while the window is open,
because it only needs the clay for renders. Mac: the same item on Metal through Storm's `HgiMetal` is the planned
path (gui-qt README). GL is the Windows shortcut proven here.

**Order.** (1) the library split plus the item drawing one scene with the engine's view post, matched pixel for pixel
against an engine `view` picture; (2) camera, pick and gizmo on it; (3) clay sculpting on it plus the stroke end on a
worker; (4) the fine-grain clay work (point 5); (5) remove the picture path from the live view.

## Attribution rows

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| Qt (qtbase, qtdeclarative), C++ SDK for msvc2022_64 | 6.12.0 | LGPL-3.0 | `proofs/3d-viewport` (C++ QML item; later Rostrum3D's viewport module) | dynamic | dev only (the apps ship PySide6's Qt) | Keep Qt dynamically linked and replaceable; ship the LGPL notice and offer the source | https://download.qt.io/online/qtsdkrepository/windows_x86/desktop/qt6_6120/ |
