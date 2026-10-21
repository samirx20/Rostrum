# Rostrum3D engine contract — the scene description

*Team Hem, brief H12, 2026-10-21. Version **1.1**. Between the Python layer (`apps/3d/python/rostrum3d/`) and the C++ core (`apps/3d/core/`, program `rostrum3d-core`).*

## 0. The document and USD: who owns what

**The Rostrum document (`.trd`, on `rostrum_core`) is the single source of truth. USD is what it compiles to.**

```
person (GUI) ─┐                                   ┌─ Storm   (viewport, fast)
agent (MCP) ──┼─ operations ─ document (.trd) ─ compile ─ scene JSON ─ rostrum3d-core ─ USD stage ─ Hydra ┼─ Cycles  (final)
script ───────┘   one history, merge on re-run          (this file)      (C++)        (in memory)      └─ Rostrum stylized
                                                                                         └─ save → .usda (hand-off)
```

- **Every change is an operation on the document** (OPERATIONS.md): one history, undo per author, script re-runs merge and never wipe what a person moved. USD never holds a value the document doesn't. So there is no second place an edit can live and get lost.
- **The core builds the stage from the scene description**, every time it is sent: one anonymous root layer, prims at `/World/<id>/<child id>…`. Item ids are prim names, so a prim path always leads back to its item (that is how "what's here" answers with an item id).
- **Imported USD stays a file.** An `import` item *references* the file (a USD reference arc); the file is never rewritten. A person's or agent's changes to an imported thing (move it, give a part another material, hide a part) are document values, compiled to **overrides in our layer**, which is stronger than the referenced file. Re-importing a newer version of the file keeps those overrides.
- **Why not make USD the source of truth?** USD layers have no notion of who changed what, no per-author undo, no three-way merge for script re-runs, no `valid_when`. Those live in `rostrum_core` and are shared with 2D, Sound and the Editor. Editing the USD stage directly would be a side door around them (AGENTS.md rules 3 and 4). USD stays what it is best at: the scene graph every renderer and every other 3D program reads.
- **Animation is the one key model** (the 2D keys: `t`, `v` or `c`, `ease`, same easing table). The Python layer evaluates the keys and **bakes every frame** of the shot into the scene description; the core writes them as USD time samples. One evaluator, no second easing table in C++, and a saved `.usda` plays the same in any USD program.

## 1. The conversation (`rostrum3d-core serve`, one JSON object per line each way)

One long-lived process. Each request is one line `{"<request>": {…}}`; each reply is one line. Errors are `{"ok": false, "error": "…"}` naming the request, the item id and the field; **the process keeps serving**. Unknown request names, renderer names, camera ids, view names or fields are errors listing what is accepted. Nothing is ever guessed.

| Request | Reply | Meaning |
|---|---|---|
| `{"scene": {…scene…}}` | `{"ok": true, "items": N, "prims": N, "frames": [start, end], "timing": {"buildMs"}}` | Load the scene, or replace the one held (Hydra's renderers stay warm). Checked whole: anything unknown fails and the held scene stays as it was. |
| `{"render": {…}}` | `{"ok": true, "frames": [{"frame", "exr", "png", "ms"}], "renderer", "camera", "timing": {"totalMs", "firstMs", "meanMs"}, "vram": {"processPeakMb", "gpuUsedMb", "gpuTotalMb"}, "ramPeakMb"}` | Render one frame or a range from a named camera (§ 3). With `"progress": true` a line `{"progress": i, "of": n, "frame": f, "ms": m}` comes after each frame, before the reply. |
| `{"pick": {"camera", "frame", "width", "height", "x", "y"}}` | `{"ok": true, "hit": true, "prim": "/World/device/screen", "item": "screen", "material": "mat_glass", "point": [x, y, z], "distance": d}` or `{"ok": true, "hit": false}` | What is at pixel (x, y), counted from the top-left of a `width × height` picture from that camera at that frame. Same answer whatever renderer drew the picture. `item` is the deepest prim on the path that is a document item; for a part of an import, `prim` names the part. |
| `{"view": {…}}` | `{"ok": true, "width", "height", "shm": {"name", "size", "offset", "bytes", "stride", "format": "rgba8", "seq", "width", "height"}, "ms"}` | One live viewport picture (§ 4), straight into shared memory for the screen. |
| `{"inspect_usd": {"file"}}` | `{"ok": true, "defaultPrim", "upAxis", "metersPerUnit", "prims": [{"path", "type", "material", "bounds": [[x,y,z],[x,y,z]]}, …], "truncated": false}` | What a USD file holds, so the Python side can turn an import into items (top-level parts, their materials and sizes). At most 2000 prims. |
| `{"save": {"file", "flatten"?: false}}` | `{"ok": true, "file"}` | Write the built stage's root layer as `.usda` / `.usdc` (with `flatten`, imports are pulled in). |
| `{"info": {}}` | `{"ok": true, "renderers": ["storm", "cycles", "stylized"], "displays": […], "views": {display: […]}, "gpu", "usd", "ocio"}` | What this build can do. |
| `{"quit": {}}` | `{"ok": true}` | End the process. |

## 2. The scene

```json
{
  "format": "rostrum-3d-scene", "version": 1,
  "shot": {"id": "hero", "fps": 24, "start": 0, "end": 47},
  "world": {"background": [0.0, 0.0, 0.0], "environment": null},
  "materials": [
    {"id": "mat_glass", "props": {"baseColor": [0.97, 0.99, 0.98], "metallic": 0, "roughness": 0, "transmission": 1, "ior": 1.52, "…": "…"}}
  ],
  "items": [
    {"id": "device", "type": "group", "props": {"x": 0, "y": 0, "z": 0, "rx": 0, "ry": -12, "rz": 0, "sx": 1, "sy": 1, "sz": 1, "visible": true},
     "anim": {"ry": [-12.0, -11.9, "… one value per frame, start..end …"]},
     "children": [
       {"id": "body", "type": "mesh", "props": {"…transform…": 0, "shape": "box", "width": 0.074, "height": 0.017, "depth": 0.098, "bevel": 0.004, "segments": 4, "material": "mat_alu"}},
       {"id": "screen", "type": "mesh", "props": {"shape": "box", "…": "…", "material": "mat_glass"}}
     ]},
    {"id": "key", "type": "light", "props": {"…transform…": 0, "kind": "rect", "width": 0.7, "height": 0.45, "color": [1, 1, 1], "intensity": 7, "exposure": 0, "temperature": 5600}},
    {"id": "cam", "type": "camera", "props": {"…transform…": 0, "focalLength": 100, "sensorWidth": 36, "dof": true, "fStop": 4, "focusDistance": 0.38, "near": 0.01, "far": 100}}
  ]
}
```

- **Units:** metres, Y up, angles in degrees, time in frames at `shot.fps` (the core's frame *n* is USD time code *n*). `start`/`end` are inclusive.
- **Colours are linear** (scene-referred, Rec.709 primaries) as three floats. The document stores `#rrggbb` (sRGB) for people; the compiler converts.
- **Every field is present** in `props` (the compiler fills in defaults), so the core has no defaults table. The fields, their types and ranges are `rostrum3d/fields.py` (the one table).
- **Transform** (every item): `x y z` (translate), `rx ry rz` (rotate, degrees, applied X then Y then Z, i.e. USD `xformOp:rotateXYZ`), `sx sy sz` (scale), `visible`. Authored as `translate`, `rotateXYZ`, `scale`, in that order. Aiming at a point is the compiler's job: it turns an aim into `rx ry rz`, frame by frame when animated.
- **`anim`**: a field listed here is animated. Its list holds one value per frame from `start` to `end` (numbers, or `[r, g, b]` for colours), written as USD time samples. The value in `props` is then ignored.
- **`children`**: items inside a `group` or an `import`; their transforms are relative to the parent.
- Ids match `[A-Za-z_][A-Za-z0-9_]*` and are unique in the scene (they are prim names).

### Item types

| type | props (besides the transform) | USD |
|---|---|---|
| `group` | — | `Xform` |
| `mesh` | `shape`: `box` (`width height depth bevel segments`), `sphere` (`radius segments`), `cylinder` (`radius height bevel segments`), `plane` (`width depth`), `disc` (`radius segments`), `torus` (`radius tube segments`); `smooth` (bool: smooth normals, or flat); `material` (id or `""`) | `Mesh` with points, normals and `primvars:st` (UVs, 0..1 per face group, so textures land), centred on its origin, made by the core |
| `import` | `file` (absolute path of a `.usd/.usda/.usdc/.usdz`), `prim` (path in the file, `""` = its default prim), `material` (id or `""`: one material over the whole import), `parts`: `[{"path": "Body/Screen", "material": "mat_x" or "", "visible": true}]` (overrides on parts, paths relative to `prim`) | `Xform` with a reference to the file; overrides in our layer |
| `light` | `kind`: `rect` (`width height`), `disk` (`radius`), `sphere` (`radius`), `distant` (`angle`), `dome` (`texture`: absolute HDR/EXR path or `""`); `color`, `intensity`, `exposure`, `temperature` (kelvin, `0` = off), `normalize` (bool), `shadows` (bool) | `UsdLux` light; rect/disk shine along their −Z |
| `camera` | `focalLength` (mm), `sensorWidth` (mm; height follows the render's aspect), `dof` (bool), `fStop`, `focusDistance` (m), `near`, `far` (m) | `Camera`; `dof: false` writes f-stop 0 (no depth of field) |

### Materials

One physically based material type, written as Cycles' `principled_bsdf` (on `outputs:cycles:surface`, the node Cycles' Hydra plug-in reads) **and** a `UsdPreviewSurface` (on `outputs:surface`, for Storm and other USD programs). Bound with `material:binding`; prim `/World/Looks/<id>`.

| prop | | notes |
|---|---|---|
| `baseColor` | [r,g,b] linear | |
| `baseColorTexture` | absolute path or `""` | sRGB image on the mesh's UVs; multiplies nothing, replaces `baseColor` |
| `metallic`, `roughness` | 0..1 | |
| `roughnessTexture` | path or `""` | raw (non-colour) |
| `transmission`, `ior` | 0..1, 1..3 | glass: `transmission 1, roughness 0, ior 1.5` |
| `coat`, `coatRoughness` | 0..1 | |
| `anisotropy`, `anisotropyRotation` | 0..1, 0..1 | brushed metal (Cycles) |
| `bumpTexture`, `bumpStrength` | path or `""`, 0..1 | a height image as bump (painted relief) |
| `emissionColor`, `emissionStrength` | [r,g,b], ≥ 0 | |
| `thinFilm` | nm, 0 = off | coatings |

## 3. Render

```json
{"render": {"camera": "cam", "renderer": "cycles", "frame": 0,
            "width": 1920, "height": 1080, "samples": 256, "denoise": true,
            "exr": "C:/…/still-{frame}.exr", "png": "C:/…/still-{frame}.png",
            "view": "", "exposure": 0, "timeoutS": 600, "progress": false}}
```

- `frame` or `frames: [first, last]` (inclusive, within the shot).
- `renderer`: `storm` (Hydra's GL renderer, fast), `cycles` (path traced, final; GPU through OptiX when the machine has it, else CPU, named in the reply), `stylized` (our Hydra plug-in, P-3D-3). Any other name is an error listing these.
- `samples`, `denoise`: Cycles only (others ignore them). A progressive renderer is rendered until it says it is done; past `timeoutS` the render fails (never a half-finished picture with success).
- **Outputs:** `exr` = scene-linear half-float RGBA OpenEXR (for the Editor); `png` = 8-bit sRGB picture through **OpenColorIO**: the config's scene-linear space to the display `sRGB`-type display and `view` (`""` = the config's default view), after `exposure` stops. At least one of `exr` / `png`. `{frame}` is replaced by the frame number (4 digits); a range needs it. The config is the one named by `OCIO`, else OpenColorIO's built-in CG config. Each file is written to `<name>.partial` and renamed when whole.
- The picture is `width × height`; the camera's sensor height follows that aspect.
- Timings are per frame and in total; video memory is this process's peak (Windows DXGI) plus the whole card's use (NVML), so the agent sees what fits on a 4 GB card.

## 4. The live viewport (`view`, H13)

```json
{"view": {"camera": "cam",                                        // look through a scene camera, OR a free camera:
          "eye": [0.3, 0.2, 0.5], "target": [0, 0, 0], "fov": 30,  // fov = vertical, degrees; up is +Y
          "frame": 12, "width": 960, "height": 540,
          "renderer": "storm", "exposure": 0, "studio": 1.0, "sceneLights": true,
          "selected": ["device"], "view": ""}}
```

- Give **either** `camera` **or** `eye` + `target` + `fov` (the free camera orbits around `target`). Near/far for the free camera follow its distance.
- `renderer`: `storm` (default) or `stylized`; Cycles is for `render`.
- `exposure` (stops) and `view` (OCIO view) as in `render`; the picture goes through OpenColorIO like the PNG does.
- `studio`: strength of the viewport's studio environment (a soft studio dome made by the core, so metal and glass have something to reflect); `0` = off. `sceneLights`: the scene's own lights on or off. Both are viewport-only: renders never see them. The studio is never seen by the camera. When the scene has its own dome light and `sceneLights` is on, that dome lights the viewport instead of the studio and is seen behind the scene, as in Cycles (core/src/sky.cpp: Storm is handed the dome's picture, or a flat one, × colour × intensity × 2^exposure × π, because Storm shows a dome π times darker than Cycles; Storm draws into its own colour picture so its sky pass runs). KNOWN OPEN (H15): an HDR dome's horizon sits about 10° lower in Storm than in Cycles.
- `selected`: item ids drawn with an outline.
- The pixels (straight-alpha RGBA8, top row first, background laid in) are written into a named shared-memory block with two slots used in turn, as in Rostrum2D's `pixels` (`Local\rostrum3d-<pid>-<n>`; Python: `mmap.mmap(-1, size, tagname=name, access=mmap.ACCESS_READ)`). The reader must be done with a slot before it asks for the view after next. Windows only for now.
- **`pick`** takes the same camera choice: `camera`, or `eye` + `target` + `fov`.

## 5. Change log

- **v1** (H12): first version.
- **v1.1** (H13): `view` (live viewport pictures in shared memory, studio light, exposure, selection outline); `pick` with a free camera; glass shows as glass in Storm.
