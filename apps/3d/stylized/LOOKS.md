# Rostrum Stylized — how to use the controls

A how-to for the controls of our Hydra render delegate "Rostrum Stylized" (`hdRostrum`). It says what each control does and how it is computed. It does not say what to make: every number below is a *default*, not advice.

Sources: `src\material.cpp`, `src\light.cpp`, `src\lights.cpp`, `src\mesh.cpp`, `src\renderPass.cpp`, `resources\shaders\{shade,edges,ink,gbuffer}.frag`, `geom.vert`. The shaders are read at run time from the install (or from `%ROSTRUM_SHADERS%`), so a shader change needs no C++ build.

Where the controls live:

| Where | What | Section |
|---|---|---|
| Each **material** (the screen's material fields; the core writes them on a `rostrum_stylized` node) | base colour / image, glow, **Lines**, **Light to colour**, **Halftone** | 2 |
| Each **light** (UsdLux) | colour, temperature, intensity, exposure, normalize, size, shadows, a spot's cone | 3 |
| The **frame** (renderer settings `rostrum:*`) | supersampling, shadow maps, background, brush strokes, frame-wide ink, paper | 5 |
| A **mesh** (constant primvars `rostrum:bend:*`) | per-camera shape bend | 6 |

Where it draws: the viewport's Look: Stylized, a render whose shot has Quality **Stylized** (the Render button, the render sheet, and an agent's `render_still` / `render_video` when it gives no `renderer` or `quality`), and any `look_frame` / `render_still` / `render_video` with `renderer: "stylized"`.

## 1. What a pixel goes through

1. **Shadow maps** for up to 4 lights (section 3.4).
2. **G-buffer**: base colour (or image), surface direction, depth, position, which object, which material.
3. **Shade**: the light reaching the pixel from every light (section 3), then the pixel's material turns it into a colour (section 2): plain, or Light to colour, then Halftone on top. "How lit" is kept beside the colour for the lines.
4. **Edges**: a line width wherever a material with Lines on has an outline or a crease (section 2.3).
5. **Ink**: the lines drawn from those widths, in each material's line colour; then paper grain (off by default).
6. Down to the output size (when `rostrum:ss` > 1) and into Hydra's colour and depth outputs.

## 2. Per-material controls

The core writes, for every material, a shader `/World/Looks/<id>/Stylized` with `info:id = "rostrum_stylized"` on the material's `outputs:rostrum:surface`. The delegate asks Hydra for the `rostrum` material context, so it reads that node. A material without it (another stage, a plain `UsdPreviewSurface`) is read as a **plain** material: its diffuse colour or image and its emissive colour only.

Colours are linear (the core converts the screen's sRGB colours).

### 2.1 Surface

| Input | What it does |
|---|---|
| `baseColor` (color3f) | The surface colour. When it is linked to an image (the core links it to the material's base-colour `UsdUVTexture`), the image is used instead (8-bit images, read as sRGB). |
| `emission` (color3f) | Glow, added after the lighting (the screen's glow colour × strength). |
| `opacity` | Read but not used: the stylized look draws every surface solid. |

A material whose only colour is its glow (black base colour, no image, none of the blocks below on) is a **glowing card**: shown exactly as its glow, never shadowed, casting no shadow, with no lines. A light's `card` panel is one of these.

**Plain** (Light to colour off): colour = base colour × the light reaching the pixel + emission. The light is physical (section 3), so a scene lit for Final (Cycles) or the Quick look (Storm) has about the same brightness here.

### 2.2 Light to colour

Paints the surface in up to three colours chosen by how lit it is, instead of shading it smoothly. The same rule is used by Final (Cycles), so both looks agree.

| Input | Default | What it does |
|---|---|---|
| `lightToColor` (bool) | off | On: the bands below replace the plain shading. |
| `litColor` | white | Colour where "how lit" ≥ `litFrom`. |
| `midColor` | `#b3b3b3` | Colour between `shadowBelow` and `litFrom`. |
| `shadowColor` | `#4d4d4d` | Colour where "how lit" < `shadowBelow`. |
| `shadowBelow` | 0.15 | Where shadow ends, on the "how lit" scale 0..1. If it is above `litFrom`, `litFrom` is used for both (no mid band). |
| `litFrom` | 0.5 | Where lit starts. |
| `lightSmooth` (bool) | off (the screen's `lightEdges = steps`) | Off: hard steps. On (`smooth`): each band edge blends linearly. |
| `lightSoftness` | 0.1 | With smooth: shadow → mid blends over `shadowBelow ± softness`, mid → lit over `litFrom ± softness`. Range 0.01..0.5. |

Colour = band colour × base colour (or image) + emission. White in a band = the base colour itself. The light's own colour does not tint the bands (it does count toward how lit, through its luminance).

**"How lit"** (the same definition in Cycles and here):

```
how_lit = clamp( Σ lights  Y(colour) · E · max(N·L, 0) · shadow
               + Σ domes   Y(colour) · E_dome · (0.5 + 0.5 · N·up) ,  0, 1 )
```

`E` is the light's brightness in "shown" units: what a white matte surface facing the light shows at exposure 0 (section 3.1). `Y` is the Rec.709 luminance of the light's colour. So how lit = 1 is a white surface that the scene's lights make look white on screen; a grey surface under the same light is still how lit 1 (how lit does not depend on the material).

### 2.3 Lines

Ink outlines and creases. Drawn only on materials with `lines` on (unless the frame-wide ink of section 5 is set).

| Input | Default | What it does |
|---|---|---|
| `lines` (bool) | off | On: this material gets lines. |
| `linesWidth` | 1.5 | Width in output pixels (0.25..12), the same at any supersampling. |
| `linesColor` | `#1a1a1a` | Line colour. |
| `linesTaper` | 0.5 | Lines thin out where the surface is lit: width × (1 − taper × smoothstep(0.25, 1, how lit)). 0 = even width; 1 = gone in full light. |
| `linesWobble` | 0.3 | Width varies along the line: width × (1 + wobble × 1.6 × noise), noise −1..1 over about 40 output pixels; where it reaches 0 the line breaks. 0 = even. |
| `linesCreaseAngle` | 40° | A fold where the surface turns sharper than this angle (between neighbouring pixels one output pixel apart) gets a crease line, fading in over the 15° below it (less for small angles). 180 = outlines only. |

Which pixels get a line: a pixel of this material whose neighbour is another object, the background, or the same object much farther away (a fold in front of itself, 5 % of the depth) is on an **outline**; only the nearer side carries it. A crease (above) gets the same width. The width is measured per pixel, then the ink pass draws a round dot of that width at every such pixel; the line is the union of the dots, coloured by the material of the pixel the dot came from.

### 2.4 Halftone

Dots or lines of one colour where the surface is not lit, laid over the plain or Light-to-colour result.

| Input | Default | What it does |
|---|---|---|
| `halftone` (bool) | off | On: the halftone is drawn. |
| `halftoneLines` (bool) | off (the screen's `halftoneShape = dots`) | Off: round dots. On: parallel stripes. |
| `halftoneSize` | 6 | Cell size in output pixels (2..40): the distance between dot centres / stripes. |
| `halftoneAngle` | 45° | Turns the grid of cells on screen (−90..90). |
| `halftoneColor` | `#1a1a1a` | The dots' / stripes' colour. |

Coverage = 1 − how lit. Dots: each cell has a dot whose radius grows with √coverage, so its area grows with coverage; at coverage 1 the dots meet the cell corners and the surface is solid. Stripes: a stripe of width coverage × cell size per cell. Fully lit = nothing drawn. The grid is fixed to the picture (screen space), in output pixels, so it doesn't change with supersampling.

## 3. Lights

### 3.1 Brightness (UsdLux units, as Storm and Cycles)

Read from each UsdLux light: `color`, `enableColorTemperature` / `colorTemperature` (blackbody tint), `intensity × 2^exposure`, `normalize`, the shape size (`width`/`height`, `radius`, the light's scale applied), a sphere light's `shaping:cone:angle` / `:softness` (a spot), `shadow:enable`.

Brightness in shown units (a white matte surface facing the light, exposure 0):

| Light | Shown brightness |
|---|---|
| Distant (sun) | intensity / π (intensity is the light on a facing surface, lux; `normalize` doesn't change it) |
| Rect | radiance × width × height / π / d², radiance = intensity (÷ width × height with `normalize`) |
| Disk | radiance × r² / d², radiance = intensity (÷ πr² with `normalize`) |
| Sphere | radiance × r² / d², radiance = intensity (÷ 4πr² with `normalize`) |
| Dome | its picture × colour × intensity: the picture's light over the upper half of the sky, cosine-weighted, / π, for a surface facing up; the lower half for a surface facing down; blended between by 0.5 + 0.5 N·up. A dome with no picture shows 1 × colour × intensity everywhere. |

`d` is the distance to the light's centre. Local lights are treated as points (no soft area light): × max(N·L, 0); rect and disk light only the side they face (× the cosine at the panel); a spot fades out between angle × (1 − softness) and its angle. Close to a light the 1/d² is capped at the light's own surface brightness. The dome's picture is read once per file (float images; any other is lit as a flat dome, with a message).

These match the hand values of `apps\3d\tools\light_check.py` (distant, flat dome, sun dome, rect, rect normalized).

### 3.2 Which lights

Up to **8 lights**, the strongest at the centre of the lit objects first; weaker ones are left out with a warning. **One dome**: the viewport hands the scene's dome to the delegate a second time (its sky), so only the brightest dome counts.

### 3.3 Legacy per-light controls (primvars)

Still read when authored on a light as constant primvars `primvars:rostrum:<name>` (the screen doesn't write them). A light with a ramp is drawn the proof's way (no fall-off, colour × gain, its own ramp); a light without one is physical (3.1).

| Name | Default | What it does |
|---|---|---|
| `rostrum:ramp:positions` (`float[]`) + `rostrum:ramp:colors` (`color3f[]`) | none | This light's own colour ramp on its "how lit" (N·L × shadow, 0..1); same length. Plain materials take ramp colour × light colour × gain. |
| `rostrum:ramp:smooth` | 0 | Softens the ramp steps (0 = hard; 1 = a blur as wide as the whole 0..1 scale). |
| `rostrum:gain` | 1 | Multiplies a ramp light's colour. |
| `rostrum:wrap` | 0 | Light reaches past the edge where a surface turns away (every light; 0 = physical). |
| `rostrum:shadow` (`bool`) | `shadow:enable` | Overrides whether this light casts shadows. |
| `rostrum:hemiUp` (`float3`) | (0, 1, 0) | Dome: the "up" of its hemisphere. |
| `rostrum:enable` (`bool`) | true | false = the light is skipped. |

### 3.4 Shadows

The first 4 lights (strongest first) whose shadows are on get a shadow map, fitted tightly around the corners of the lit objects' box as that light sees it (a light among the objects gets a 160° map). The map is drawn with a slope offset, so a face the light only grazes doesn't shadow itself in steps. Domes cast none. Glowing cards cast none. Settings: `rostrum:shadow:size`, `:soft`, `:offset` (section 5).

## 4. "How lit" in the picture

It is kept in the shaded picture's alpha (0..1) and used by the lines' taper; Light to colour and Halftone read it directly. Brush strokes (section 5) nudge it before the bands.

## 5. Frame-wide settings (renderer settings `rostrum:*`)

Name = `rostrum:<group>:<name>`; in the shaders it becomes `u_<group>_<name>`. A colour is sent as `…:x`, `…:y`, `…:z`. The core sends `rostrum:ss` and `rostrum:shadow:size`; the proof's `render.py` sends every authored `rostrum:*` attribute of a `/RostrumLook` prim.

| Setting | Default | What it does |
|---|---|---|
| `rostrum:ss` | 2 | Supersampling: renders at this multiple of the size (1–4) and filters down. The viewport sends 1; a render sends its `supersample` (default 2). Higher = smoother lines, slower, more video memory (section 7). |
| `rostrum:shadow:size` | 2048 | Shadow-map size in pixels (256–8192), one square map per shadowed light. |
| `rostrum:shadow:soft` | 1.5 | Shadow edge softness, in shadow-map texels (a 5×5 blur). |
| `rostrum:shadow:offset` | auto | Pushes the shadow lookup off the surface, in scene units. Unset (or below 0): 8 texels of that light's map where the lit objects are, so a 25 cm product and a room both work. Raise if surfaces speckle with their own shadow; lower if shadows detach. |
| `rostrum:bg:color` | (0, 0, 0) | Colour where nothing is drawn, when the camera doesn't see a dome. A dome the camera sees is shown instead, as Storm and Cycles show it: its picture by view direction (USD's lat-long, the dome's `turn` applied) × colour × intensity, or its colour × intensity without a picture. |
| `rostrum:brush:amount` | 0 | Brush strokes push "how lit" up and down (Light to colour and legacy ramps; plain shading is not changed). 0 = off. |
| `rostrum:brush:length` / `:width` | 18 / 3 | Stroke size, output pixels. |
| `rostrum:brush:angle` / `:follow` | 35 / 0.7 | Fixed stroke angle on screen; 0 = all strokes at the angle, 1 = follow the form. |
| `rostrum:ink:width` | 0 (off) | > 0: lines on **every** material that has no Lines of its own, this wide (output pixels), with `ink:creaseAngle` (35), `ink:lightTaper` (0.6), `ink:wobble` (0.4) and `ink:color` (`#1a1a1a`). Materials with their own Lines keep theirs. |
| `rostrum:ink:crease` | 1 | Crease-line width relative to outlines, every material. |
| `rostrum:ink:creaseSoft` | 15 | Degrees over which a crease fades in. |
| `rostrum:ink:depthJump` | 0.05 | Relative depth step that counts as an outline on one object. |
| `rostrum:ink:depthTaper` | 0 | Lines thin out with distance (nearest to farthest lit object). |
| `rostrum:ink:wobbleScale` | 40 | Size of the wobble along a line, output pixels. |
| `rostrum:ink:opacity` | 1 | How strongly lines cover the picture. |
| `rostrum:ink:albedoMix` / `:albedoDark` | 0 / 0.3 | 0 = the line colour; 1 = the surface colour under the line × `albedoDark`. |
| `rostrum:paper:amount` / `:scale` | 0 / 1.5 | Paper grain (picture × (1 + amount × grain)), grain size in output pixels. 0 = off. |

## 6. Per-camera shape bend (on meshes)

Constant primvars on a mesh (usually in a shot layer as an `over`):

| Primvar | Default | What it does |
|---|---|---|
| `rostrum:bend:camera` (`string`) | none | The camera path the bend belongs to; it applies only when that camera renders. |
| `rostrum:bend:squash` | 1 | Scales height on screen (< 1 squashes); width the other way, keeping the volume. |
| `rostrum:bend:lean` (`float2`) | (0, 0) | Shear with height above the pivot: x sideways on screen, y toward (+) / away from (−) the camera. |
| `rostrum:bend:swell` | 0 | Grows (+) / shrinks (−) in the picture plane around the pivot. |
| `rostrum:bend:pivot` (`float3`) | bounds bottom-centre | World point to bend around; parts that bend together share it. |

The bend also moves the shadow casters; lighting uses the un-bent normals.

## 7. Speed and video memory

What is kept between frames: shader programs, mesh buffers, images (by path), the render targets (re-made only when the size or `ss` changes), the material table (re-sent only when a material changes), and the **shadow maps**, which are redrawn only when a light, a mesh, a glowing card or (with a bend) the bending camera changes, so turning the viewport camera or editing a material does not redraw them. The edges pass is skipped when no material has lines; at 1× the ink pass writes straight into the output.

Estimated cost at **1300 × 650, ss 1** (the viewport; 0.85 M pixels; RTX 3050 Laptop), by reasoning from the passes, not measured:

| Pass | Cost |
|---|---|
| Shadow maps | 0 when nothing changed; about 1–2 ms for 4 maps of 2048² when redrawn |
| G-buffer | about 0.5–1 ms (writes 44 bytes a pixel) |
| Shade | about 1–3 ms (25 shadow taps per shadowed light per pixel) |
| Edges | about 0.3 ms, only with lines |
| Ink | about 0.5–1 ms at 1.5 px lines (49 taps a pixel); about 5–8 ms at 12 px lines (441 taps) |
| Read-back of colour + depth | about 1–2 ms (6.8 MB + 3.4 MB to CPU memory) |
| **Frame** | **about 4–8 ms** typical, plus Hydra's sync and the host's own upload |

Video memory at 1300 × 650, ss 1: G-buffer 37 MB, shaded 7 MB, edges 2 MB, output 10 MB, shadow maps 64 MB (4 × 2048², only once a light casts) ≈ **120 MB** plus meshes and images. A 1920 × 1080 render at ss 2: ≈ 540 MB + shadows.

`ROSTRUM_DEBUG=1` prints one line per frame, `[rostrum] passes ms (W×H ss N, L lights, S shadowed): prep … shadows … gbuffer … shade … edges … ink … down …`, and the whole frame with the read-back. (It waits for the GPU after each pass, so frames are slightly slower with it on.)

The colour still goes back through CPU memory and the host uploads it again. Handing Hydra the GPU picture directly (`HdRenderBuffer::GetResource` returning an `HgiTextureHandle`, which `HdxAovInputTask` would use as is) needs a texture made through the host's Hgi (`HdRenderDelegate::SetDrivers`); whether the colour-correction and present tasks then work on it, and whether the core's own AOV reads (`aovs.cpp`, `Map()`) still get pixels, can't be checked from the headers alone, so it is not done.

## 8. Limits

- At most 8 lights (the strongest), 4 with shadows, 1 dome. Local lights are points: no soft area-light shading, sharp-ish shadows from the map.
- A dome's light is a hemisphere blend, not image-based: no direction within the sky except up/down.
- No transparency (`opacity` is not used), no reflections or refraction. Base-colour images: 8-bit only.
- The bend lights with the un-bent normals.
- Line search radius is capped at 32 rendered pixels, so a 12 px line at ss 4 is clipped.

## 9. Build

`build.bat` (through the lock; see its header) builds against the library folder's `sdk\` (`%USERPROFILE%\.rostrum\libs\3d\5.2.2-cycles-a456b76-r4\sdk`, or `%ROSTRUM3D_SDK%`) into `apps\3d\stylized\.build\install\` (`hdRostrum.dll`, `plugInfo.json`, `hdRostrum\resources\{plugInfo.json,shaders}`). The core puts that folder on `PXR_PLUGINPATH_NAME` (override `ROSTRUM3D_STYLIZED`).
