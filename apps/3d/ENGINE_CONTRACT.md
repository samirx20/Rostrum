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
| `{"pick": {"camera", "frame", "width", "height", "x", "y"}}` | `{"ok": true, "hit": true, "prim": "/World/device/screen", "item": "screen", "material": "mat_glass", "point": [x, y, z], "normal": [x, y, z], "distance": d}` or `{"ok": true, "hit": false}` | What is at pixel (x, y), counted from the top-left of a `width × height` picture from that camera at that frame. Same answer whatever renderer drew the picture. `item` is the deepest prim on the path that is a document item; for a part of an import, `prim` names the part. `normal` is the surface's direction at `point` (world space, unit length, turned toward the camera: the side that was clicked), so a shape can be stood on it. |
| `{"view": {…}}` | `{"ok": true, "width", "height", "shm": {"name", "size", "offset", "bytes", "stride", "format": "rgba8", "seq", "width", "height"}, "ms", "final", "vram": {"processMb", "gpuUsedMb", "gpuTotalMb"}, …}` | One live viewport picture (§ 4), straight into shared memory for the screen. `final` is `null` for Storm / stylized; with Cycles (the Final look) it is `{"fraction": 0..1, "converged", "samples" (done), "of", "seconds", "cyclesMb", "status"}`. |
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
- **`children`**: items inside a `group` or an `import`; their transforms are relative to the parent. A `combine`'s children are its inputs (below), not items of their own.
- Ids match `[A-Za-z_][A-Za-z0-9_]*` and are unique in the scene (they are prim names).

### Item types

| type | props (besides the transform) | USD |
|---|---|---|
| `group` | — | `Xform` |
| `mesh` | `shape`: `box` (`width height depth bevel segments`), `sphere` (`radius segments`), `cylinder` (`radius height bevel segments`), `cone` (`radius height segments`: base radius, base to point), `capsule` (`radius height segments`: height end to end, at least `2 × radius`, else fails loudly), `plane` (`width depth`), `disc` (`radius segments`), `torus` (`radius tube segments`), `outline` (`outline depth bevel segments` + four face materials, see below); `smooth` (bool: smooth normals, or flat); `material` (id or `""`) | `Mesh` with points, normals and `primvars:st` (UVs, 0..1 per face group, so textures land), centred on its origin, made by the core |
| `combine` (v1.6) | `op`: `union`, `subtract` or `intersect`; `material` (id or `""`); `children`: 2 or more `mesh` or nested `combine` nodes, the first being the base. `anim` animates the combine's own transform and `visible`, as for a group | One `Mesh` at the combine's path, made by the core with Manifold (core/src/boolean.cpp, stage_combine.cpp): triangles, vertex normals, `primvars:st` carried over from the inputs (cut faces keep the cutter's UVs, normals turned to face out) |
| | **Inputs (children).** Each child is an ordinary `mesh` node (all its usual props) or a `combine`, placed in the combine's space by its own transform (`x y z rx ry rz sx sy sz`). Children are **inputs only**: never prims, never rendered; their ids still count as scene ids (unique). A child's `visible`, `material` and face materials are read and ignored: the result wears the combine's `material`. `union` joins all; `subtract` = the first minus all the rest; `intersect` keeps only what every child shares. **Fails loudly:** fewer than 2 children (`<id>.children: N children`); a child with `anim` (`<child>: an input of combine '<id>' can't be animated yet; key the combine itself`); a child that isn't a closed solid — `plane`, `disc`, an outline of depth 0 (`<id>: '<child>' is not a closed solid (it has open edges or holes), so it can't be combined. Accepted: closed shapes as inputs: box, sphere, cylinder, torus, text or svg with depth > 0, or another combine …`); an empty result (`<id>: Subtract gave an empty shape: '<cutters>' cover '<first>' entirely`, `<id>: Intersect gave an empty shape: '<a>' and '<b>' don't overlap`). |
| `import` | `file` (absolute path of a `.usd/.usda/.usdc/.usdz`), `prim` (path in the file, `""` = its default prim), `material` (id or `""`: one material over the whole import), `parts`: `[{"path": "Body/Screen", "material": "mat_x" or "", "visible": true}]` (overrides on parts, paths relative to `prim`) | `Xform` with a reference to the file; overrides in our layer |
| `light` | `kind`: `rect` (`width height`), `disk` (`radius`), `strip` (`length` along its X, `width` along its Y; v1.3), `sphere` (`radius`), `spot` (`radius`, `cone` full angle in degrees 1..179, `softness` 0..1), `distant` (`angle`), `dome` (`texture`: absolute HDR/EXR path or `""`; `seenByCamera` bool, v1.3); `color`, `intensity`, `exposure`, `temperature` (kelvin, `0` = off), `normalize` (bool), `shadows` (bool); v1.3, every kind (used where it applies): `spread` (degrees 0..180, rect/disk/strip), `card` (bool, rect/disk/strip), `lightsOnly` (item ids separated by spaces, `""` = everything; not domes) | `UsdLux` light; rect/disk/spot shine along their −Z. **`spot`**: a `SphereLight` with `UsdLuxShapingAPI` `shaping:cone:angle` = cone / 2 and `shaping:cone:softness` = softness (both animatable). **Not yet drawn as a cone** (2026-10-24): Storm lights it all around like a bulb, and our Cycles Hydra plug-in build ignores the shaping cone on sphere lights too (it needs `cycles-rostrum-lights.patch` to set the Cycles spot light's angle = cone and smooth = softness, and a rebuild of the plug-in). **Units are UsdLux's in every renderer** (H19): a dome of intensity 1 is seen as its picture's own values; a distant light with `normalize` on gives `intensity` lux on a surface facing it (a white floor then shows intensity / π); area lights: `intensity` is their brightness (normalize off). Cycles' Hydra plug-in reads domes and distant lights differently, so a filter in front of Cycles alone corrects them (core/src/cycles_lights.h); checked against hand-computed values by `apps/3d/tools/light_check.py` |
| | **Product lighting (v1.3, H21; core/src/light_extras.h).** A dome's turn is its `ry` (the document's `turn`; its `rx`, `rz` are 0). | **`strip`**: a `RectLight` (width = `length`, height = `width`). **`spread`** < 180: `UsdLuxShapingAPI` cone angle = spread / 2 (180 authors nothing). **`card`**: `rostrum:card = true` on the light plus a `RostrumCard` mesh under it (the panel's size, facing −Z, glowing at the light's own brightness frame by frame, material `RostrumCardGlow` under the light). **`lightsOnly`**: `rostrum:lightsOnly` and the light's `collection:lightLink` (`includeRoot` false, `includes` = those items' prims); an id that is no item of the scene (or the light itself) fails the scene. **`seenByCamera`**: `rostrum:seenByCamera` on the dome. **Cycles** gets these through the filter in front of it (core/src/cycles_lights.cpp) and **our patch on its Hydra plug-in** (`apps/3d/libs/cycles-rostrum-lights.patch`; without the patched plug-in Cycles ignores spread, links and `seenByCamera` off): card = the light's own camera visibility (Cycles shows area lights in glossy reflections whether or not), spread = the area light's spread, links = Cycles light sets (one receiver set per distinct combination of lights linking an item, at most 63), a dome not seen = background hidden from camera rays with a clear film there (the shot's `background` shows), still lighting and reflecting. The `RostrumCard` mesh is hidden from Cycles. **Storm** (viewport and Storm renders): strip yes; card yes, as the mesh (seen by the camera; no reflections of it, Storm reflects only the dome); a dome not seen: lights, not drawn; **spread and light linking: no** (Storm lights with simplified point-like lights and every light lights everything): the `view` reply's `notInQuickView` names each such light. |
| `camera` | `focalLength` (mm), `sensorWidth` (mm; height follows the render's aspect), `dof` (bool), `fStop`, `focusDistance` (m), `near`, `far` (m) | `Camera`; `dof: false` writes f-stop 0 (no depth of field) |

### Extruded outlines (v1.3)

Shape `outline`: a flat 2D outline (text, a logo) pushed out into a solid with rounded edges (core/src/extrude.*, outline_offset.*). The Python side turns text, SVG and drawn paths into it; the core only extrudes.

```json
{"shape": "outline", "smooth": true, "depth": 0.01, "bevel": 0.002, "segments": 24,
 "outline": [{"outer": [[0, 0], [0.05, 0], [0.05, 0.07], [0, 0.07]],
              "holes": [[[0.01, 0.01], [0.01, 0.03], [0.04, 0.03], [0.04, 0.01]]]}],
 "material": "mat_gold", "frontMaterial": "", "bevelMaterial": "", "sideMaterial": "mat_dark", "backMaterial": ""}
```

- `outline`: a list of shapes, each one `outer` contour and its `holes` (each a list of `[x, y]`, metres, in the item's XY plane, front facing +Z). Curves arrive already flattened; no repeated closing point. Outers go counter-clockwise and holes clockwise seen from +Z, but the core fixes the direction itself by signed area. Checked loudly: a contour has at least 3 different points (repeats in a row are dropped), finite numbers and some area; the edges of one shape (outer and its holes) never cross. Overlapping parts of one glyph must be merged before they are sent. Separate shapes may overlap (they are separate solids).
- `depth` ≥ 0, along Z, centred: front cap at +depth/2, back cap at −depth/2. `0` = a flat card, front and back faces only.
- `bevel`: a rounded edge (quarter circle) on the front and back. 0 ≤ `bevel` ≤ depth/2. Each cap is the outline moved `bevel` inwards (along each corner's mitred direction, so straight edges stay straight; a needle-sharp corner moves at most 4 × `bevel`); the bevel rounds out to the full outline, and the side wall runs between the two bevels. When the moved outline of a shape would cross itself or turn inside out, the scene fails naming the shape and the largest bevel that works.
- `segments`: steps around each bevel = clamp(`segments`, 1, 16), the same meaning as a box's bevel, capped (the outline's curves are already flattened, so `segments` sets nothing else here).
- `smooth`: side and bevel normals are smooth along curves and split where the outline turns more than 30° (an L has hard corners, an O is smooth); caps are always flat. `smooth: false` = every face flat.
- UVs (`st`): caps 0..1 over the bounding box of the whole outline (the back mirrored, so a texture reads right from behind); side and bevel: u = distance along each contour divided by its length, v = 0 at the back edge to 1 at the front edge.
- **Face materials** `frontMaterial`, `bevelMaterial`, `sideMaterial`, `backMaterial`: a material id or `""`. `""` = the mesh's `material`; for `bevelMaterial`, `""` = the front's material. The mesh gets `GeomSubset`s of faces (family `materialBind`, type `partition`; named `front`, `bevel`, `side`, `back`, an empty one left out), each bound to its material; `material` stays bound on the mesh too. Storm and Cycles both read them.
- Other shapes are sent these fields too (every field is present) and ignore them.

### Materials

One physically based material type, written as Cycles' `principled_bsdf` (on `outputs:cycles:surface`, the node Cycles' Hydra plug-in reads) **and** a `UsdPreviewSurface` (on `outputs:surface`, for Storm and other USD programs). Bound with `material:binding`; prim `/World/Looks/<id>`.

| prop | | notes |
|---|---|---|
| `baseColor` | [r,g,b] linear | |
| `baseColorTexture` | absolute path or `""` | sRGB image on the mesh's UVs; multiplies nothing, replaces `baseColor` |
| `metallic`, `roughness` | 0..1 | Cycles' principled BSDF has **one** roughness: on glass it also blurs what is seen through (frosted glass) |
| `roughnessTexture` | path or `""` | raw (non-colour) |
| `transmission`, `ior` | 0..1, 1..3 | glass: `transmission 1, roughness 0, ior 1.5`; frosted: the same with `roughness` 0.1–0.4 |
| `coat`, `coatRoughness` | 0..1 | |
| `coatTint`, `coatIor` | [r,g,b] linear, 1..3 | Cycles `coat_tint`, `coat_ior`; Storm: none (its clear coat is untinted, fixed IOR) |
| `sheen`, `sheenRoughness`, `sheenTint` | 0..1, 0..1, [r,g,b] | Cycles `sheen_weight`, `sheen_roughness`, `sheen_tint`; Storm: none |
| `anisotropy`, `anisotropyRotation` | 0..1, 0..1 | brushed metal (Cycles) |
| `brushDirection` | `"uv"`, `"around x"`, `"around y"`, `"around z"` | where the brushing runs, linked into the principled `tangent` when `anisotropy` > 0. `uv`: a `cycles_tangent` (`direction_type uv_map`, default UVs). `around <axis>`: circles round that axis of the item through its origin, built as `cycles_texture_coordinate.object` × axis (`cycles_vector_math cross_product`) → `cycles_vector_transform` object→world. (Cycles' own radial tangent centres its circles on generated coordinate 0.5, which Hydra meshes don't have.) Storm: none |
| `bumpTexture`, `bumpStrength` | path or `""`, 0..1 | a height image as bump (painted relief) |
| `emissionColor`, `emissionStrength` | [r,g,b], ≥ 0 | |
| `emissionTexture` | path or `""` | an sRGB image on the UVs that becomes the glow colour (× `emissionStrength`): Cycles `cycles_image_texture` → `emission_color`; Storm a `UsdUVTexture` (scale = strength) → `emissiveColor` |
| `thinFilm` | nm, 0 = off | coatings |

**A picture per frame** (v1.4): a material may carry `"anim": {"emissionTexture": [one absolute image path per frame, start..end]}`; no other material field can change per frame. The core writes them as **time samples on the texture's file input** (Cycles `filename`, Storm `file`; asset paths are held, never blended), so one stage plays the whole shot like every other animated field. Both renderers read material inputs through UsdImaging, which should mark a time-sampled shader input as varying and re-read it when the frame changes. **Not yet seen working (H22):** the materials turntable video (`tools/materials_turntable.py video`) is the check: its screen shows its own 2D frame number. If the screen stays on one picture, the fallback is to send one scene per frame for shots that use it. Every path is checked (absolute, exists) before anything is built.

The document's `emissionRender` (the id of a 2D item of the project) never reaches the core: the compiler (`material_scene.py`) takes that item's newest finished `pictures` render (`rostrum_core.project.latest_render`), which must be a PNG sequence, and gives each shot frame *f* the 2D file of the same moment: `first + floor((f / fps − frames.start) × fps2)`, held at the first and last file. A still render gives one `emissionTexture`; a sequence gives the `anim` list. Loud: no project folder, no such item, not a 2D item, not rendered, no PNG frames, a frame file missing.

**Storm can't show:** anisotropy and its direction, sheen, coat tint and coat IOR, thin film, bump. Rough glass can't blur what is behind it in Storm, so it is drawn less see-through and milkier the rougher it is (`see_through = transmission × (1 − 0.6 × roughness)` sets both the diffuse share and the opacity).

## 3. Render

```json
{"render": {"camera": "cam", "renderer": "cycles", "frame": 0,
            "width": 1920, "height": 1080, "samples": 256, "denoise": true,
            "exr": "C:/…/still-{frame}.exr", "png": "C:/…/still-{frame}.png",
            "view": "", "exposure": 0, "timeoutS": 600, "progress": false}}
```

- `frame` or `frames: [first, last]` (inclusive, within the shot).
- `renderer`: `storm` (Hydra's GL renderer, fast), `cycles` (path traced, final; GPU through OptiX when the machine has it, else CPU, named in the reply), `stylized` (our Hydra plug-in, P-3D-3). Any other name is an error listing these.
- **Domes are the same in every renderer (H16).** Storm and the stylized renderer get the scene's dome exactly as the live viewport does (seen behind the scene and lighting it, `core/src/sky.cpp`), so a Storm render equals the quick view. Cycles' Hydra plug-in reads a dome's picture with +Z up (Blender's way) where USD and Storm use +Y up; a Hydra filter in front of Cycles alone turns every dome to match (`core/src/dome_cycles.*`), so the horizon and the sun sit in the same place in both. Storm limits that remain: no reflections of other objects (a mirror ball shows only the sky), no shadows or contact darkening from the dome's sky. The small bright sun of an HDR is taken out of Storm's dome and drawn as a distant light with a shadow map (H17, § 4 `sun`), so it lights and shades like Cycles' sun, with a harder shadow edge.
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
          "selected": ["device"], "view": "", "ao": 1.0, "aoRadius": 0.3, "dof": true}}
```

- Give **either** `camera` **or** `eye` + `target` + `fov` (the free camera orbits around `target`). Near/far for the free camera follow its distance.
- `renderer`: `storm` (default), `stylized`, or `cycles` (the Final look, below).
- **Final look (v1.5)**: with `renderer: "cycles"` each `view` request does one step of progressive Cycles and returns at once with the picture as far as it has got; sending the same request again carries on, and any change (scene, camera, frame, size, settings) starts it over. `samples` (1..65536, default 128) and `denoise` (default true) belong to it; given with any other renderer they are an error. Through a scene `camera` it takes the camera's own path exactly as `render` does (same lens, depth of field from Cycles itself), so it matches the Render button; a free camera works too. The viewport-only extras are off: no contact shading (`ao`), no viewport depth-of-field blur, no selection outline, no studio light (the scene's own lights light it). `exposure` and `view` still apply as sent. The reply's `final` and `vram` fields are listed in § 1. The process keeps its Cycles engine until it ends: to give the graphics memory back, the screen ends the viewport's engine process on leaving Final (`Engine.release()`; a fresh one draws Quick), because ending one Hydra Cycles engine inside a running process crashed it.
- `exposure` (stops) and `view` (OCIO view) as in `render`; the picture goes through OpenColorIO like the PNG does, on the graphics card (H20, core/src/view_post.* and ocio_gpu.*: the same config, display and view as the PNGs, as a shader; measured within 1/255 of the CPU path).
- `ao` (H20): contact shading (screen-space ambient occlusion, from Storm's depth) strength 0..2, default 1; `0` = off. `aoRadius`: how far it reaches, in scene units (default 0.3). Viewport-only, because Storm has no ambient occlusion of its own: without it a ball on a floor under an even sky reads flat. It darkens what the camera sees of corners and contacts; what is hidden on screen (the floor under a ball) can't darken anything.
- `dof` (H20, default true): depth of field when looking through a scene `camera` whose depth of field is on (its f-stop, focus distance, focal length and sensor width; thin-lens blur, matching Cycles' blur behind the focus). A blurred object in front of the focus doesn't spread over the sharp things around it, unlike Cycles. The reply's `cameraDof` says whether the camera looked through has depth of field on (the screen shows its Depth of field switch only then). The reply's `notInQuickView` (v1.3) lists the scene's product-lighting settings Storm can't show (a light's `spread`, its `lightsOnly`), one line per light, `[]` when none.
- `studio`: strength of the viewport's studio environment (a soft studio dome made by the core, so metal and glass have something to reflect); `0` = off. `sceneLights`: the scene's own lights on or off. Both are viewport-only: renders never see them. The studio is never seen by the camera. When the scene has its own dome light and `sceneLights` is on, that dome lights the viewport instead of the studio and is seen behind the scene, as in Cycles (core/src/sky.cpp: Storm is handed the dome's picture, or a flat one, × colour × intensity × 2^exposure (× its colour temperature), because Storm reads only a dome's picture; Cycles gets the same picture; Storm draws into its own colour picture so its sky pass runs). The reply's `sceneDome` (true / false) says whether the scene's dome lit this picture, i.e. the studio was not used (the screen hides its Studio light slider then). In Storm, a dome picture whose light sits mostly in one small bright patch (a sun) is split once per picture (core/src/dome_sun.cpp, cached as `%USERPROFILE%\.rostrum\cache\3d\domesun-v1-*`): the patch is painted over with the sky around it, and Storm gets, beside that picture, a distant light with a shadow carrying exactly the light taken out (core/src/storm_sun.cpp), so the total light is unchanged; Cycles and the stylized renderer keep the whole dome. The reply's `sun` is then `{"toward": [x, y, z] (world direction towards the sun), "share": 0..1 (its part of the dome's light), "angleDeg": its apparent size}`, else `null`. A Storm `render` gets the same sun.
- `selected`: item ids drawn with an outline (a 2-pixel ring in the kit's accent colour).
- The pixels (straight-alpha RGBA8, top row first, background laid in; read straight from the graphics card into the slot) are written into a named shared-memory block with two slots used in turn, as in Rostrum2D's `pixels` (`Local\rostrum3d-<pid>-<n>`; Python: `mmap.mmap(-1, size, tagname=name, access=mmap.ACCESS_READ)`). The reader must be done with a slot before it asks for the view after next. Windows only for now.
- **`pick`** takes the same camera choice: `camera`, or `eye` + `target` + `fov`.

## 5. Change log

- **v1** (H12): first version.
- **v1.1** (H13): `view` (live viewport pictures in shared memory, studio light, exposure, selection outline); `pick` with a free camera; glass shows as glass in Storm.
- **v1.2** (H20): `view` finishes its picture on the graphics card (10 -> 96 pictures a second at 960 x 540); `ao`, `aoRadius`, `dof`; reply `cameraDof`.
- **v1.3** (H21): outline meshes (mesh shape `outline`: extruded, rounded-bevel text and logos with front / bevel / side / back materials).
- **v1.3** (H21): product lighting: light kind `strip`; `spread`, `card`, `lightsOnly` on lights, `seenByCamera` on domes; `view` reply `notInQuickView`. Cycles needs the patched Hydra plug-in for spread, links and a hidden dome.
- **v1.5** (Priyam brief 12): `view` renderer `cycles` (the Final look: progressive, one step per request), `samples`, `denoise`; reply `final` and `vram`; leaving Final, the screen ends the engine process (`Engine.release()`) so its graphics memory goes back.
- **v1.6** (Priyam brief 6): item type `combine` (live booleans: union, subtract, intersect of closed meshes, with Manifold 3.5.4).
- **v1.4** (H22): materials: `coatTint`, `coatIor`, `sheen`, `sheenRoughness`, `sheenTint`, `brushDirection`, `emissionTexture`, and a material's `anim.emissionTexture` (a picture per frame).
