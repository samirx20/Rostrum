# Rostrum Stylized — how to use the controls

A how-to for the controls of our Hydra render delegate "Rostrum Stylized". It says what each control does and how to use it. It does not say what to make. Every number below is a *default*, not advice.

Sources it was read from: `src\light.cpp`, `src\lights.cpp`, `src\mesh.cpp`, `src\renderPass.cpp`, `src\delegate.cpp`, `src\gl.cpp`, `resources\shaders\{shade,edges,ink}.frag`, `geom.vert`, and `render.py`.

## 1. How a look is applied (the scene is never changed)

A look is its own USD layer. You pass it with:

```
render.py <stage.usda> <out.png> --look <layer.usda>
```

`render.py` does two things with it:

1. **Adds it to the stage's session layer.** Its `over`s on lights and meshes win over the scene, but the scene file stays untouched. Use this for per-light controls (section 3) and per-mesh bend (section 5).
2. **Reads every authored `rostrum:*` attribute on the prim `/RostrumLook`** and sends each to the renderer as a setting (section 4). Only attributes with an authored value are sent; everything else keeps its default.

To compare looks, render the same stage with different `--look` layers and put the results side by side with `compose.py` (section 9).

## 2. Skeleton of a look layer (syntax only — not a look)

```usda
#usda 1.0
over "World"
{
    over "Lights"
    {
        over "SomeLight"
        {
            float[] primvars:rostrum:ramp:positions = [0, 0.5]
            color3f[] primvars:rostrum:ramp:colors = [(0.2, 0.2, 0.2), (1, 1, 1)]
            float primvars:rostrum:ramp:smooth = 0
        }
    }
}
def Scope "RostrumLook"
{
    float rostrum:ink:width = 1.6
}
```

Notes:
- The light's path must match the scene's path (`over` follows the same names). `/RostrumLook` sits at the stage root.
- The `ramp:positions` and `ramp:colors` arrays must be the same length; if not, the renderer warns and ignores the ramp.
- Colour settings are `color3f` (or `float3`) attributes, e.g. `color3f rostrum:ink:color = (0.1, 0.1, 0.1)`.

## 3. Controls authored on a light

Author them as `primvars:rostrum:<name>` on a UsdLux light. (Custom `inputs:rostrum:<name>` attributes do **not** reach Hydra in this USD build: UsdImaging passes only the light's known inputs. The delegate still asks for them first, so a future USD that passes them would work.)

| Name | Default | What it does |
|---|---|---|
| `rostrum:ramp:positions` (`float[]`) | none | Where each ramp colour starts, on the "how lit" scale 0 (dark) to 1 (fully lit). Ascending. The first colour also holds below the first position. |
| `rostrum:ramp:colors` (`color3f[]`) | none | The colour for each position. Same length as `positions`. With no ramp the light is plain smooth shading (the "how lit" value itself, as grey). |
| `rostrum:ramp:smooth` (`float`) | 0 | Softens the steps. 0 = hard steps; 1 = a blur as wide as the whole 0–1 scale. |
| `rostrum:gain` (`float`) | 1 | Multiplies the light's colour. (The USD `intensity` and `exposure` inputs are not read.) |
| `rostrum:wrap` (`float`) | 0 | Lets light reach past the edge where a surface turns away. 0 = ends exactly at the edge; higher = further round. Not used by dome lights. |
| `rostrum:shadow` (`bool`) | true (false for dome) | Whether this light casts shadows. Dome lights never cast. |
| `rostrum:hemiUp` (`float3`) | (0, 1, 0) | Dome lights only: the "up" direction of the hemisphere, in world space. |
| `rostrum:enable` (`bool`) | true | false = the light is skipped. |

Colour and colour temperature are read from the usual UsdLux `inputs:color`, `inputs:enableColorTemperature`, `inputs:colorTemperature`. The light's final colour is `color × gain`; the ramp colour is multiplied by it.

How a ramp is built (`src\lights.cpp`): each colour holds from its position to the next (a step function). With `smooth > 0` the steps are averaged over a window of width `smooth` (64 samples), so edges turn into gradients. The ramp is sampled with the "how lit" value.

## 4. How lit is computed (`shade.frag`)

For each light, the shader makes a single "how lit" number from 0 to 1. Then the brush strokes nudge it (section 4.2), then the light's ramp turns it into a colour. Final colour = surface colour (albedo) × the sum of every light's ramp colour × light colour.

### 4.1 Per light type

- **Distant:** `clamp((N·L + wrap) / (1 + wrap), 0, 1)`, where `L` is the direction to the light (opposite to where it shines) and `N` the surface normal. Times shadow.
- **Sphere:** the same, but `L` points from the surface to the light's position. No falloff with distance; the size/radius is not used.
- **Rect / disk:** treated as a point light at its position (like a sphere), but **one-sided**: it only lights surfaces on the side it faces (its local −Z). The one-sided factor is `clamp(dot(facing, −L) × 3, 0, 1)`, so there is a short fade at the sideways edge. Size and shape are not used.
- **Dome:** `0.5 + 0.5 × (N · hemiUp)`: surfaces facing `hemiUp` are 1, facing away are 0, sideways 0.5. No wrap, no shadow, and the dome's transform and texture are not used.

Shadows (point/distant/rect/disk lights with `rostrum:shadow` true): the result is multiplied by the shadow value (0 = in shadow). Two settings, `shadow:soft` and `shadow:offset`, in section 6.

### 4.2 Brush strokes

Before the ramp lookup: `lit = clamp(lit + brush:amount × stroke, 0, 1)`, where `stroke` is a pattern between −1 and +1 made of elongated noise streaks drawn in screen space (the pattern stays fixed to the picture, not to the object).
- `brush:amount` is how far a streak can push light up or down. 0 = off. Around a ramp step, a streak pushes some pixels across the step, so the step's edge looks painted instead of clean.
- `brush:length` / `brush:width` set the streak size in output pixels.
- Direction: `brush:angle` is a fixed screen angle. `brush:follow` blends toward the direction that follows the form (around the contour of the surface as seen from the camera); 0 = all strokes at the angle, 1 = follow the form. Where the surface faces the camera head-on, there is no form direction and the angle is used.

## 5. Per-camera shape bend (on meshes)

For a shape that should be drawn differently from one camera than from another. Author these as **constant primvars** on a mesh (a `primvars:rostrum:bend:...` attribute, interpolation `constant`; usually in the look layer as an `over`):

| Primvar | Default | What it does |
|---|---|---|
| `rostrum:bend:camera` (`string`) | none | The path of the camera this bend belongs to, e.g. `/World/Cam1`. The bend applies only when the render camera has exactly this path. No camera = no bend. |
| `rostrum:bend:squash` (`float`) | 1 | Scales height on screen. Below 1 squashes, above 1 stretches. Width shrinks/grows the other way to keep the volume. |
| `rostrum:bend:lean` (`float2`) | (0, 0) | Shear, proportional to height above the pivot. `x` leans sideways on screen; `y` leans toward (+) or away from (−) the camera. |
| `rostrum:bend:swell` (`float`) | 0 | Grows (+) or shrinks (−) the shape in the picture plane, around the pivot. |
| `rostrum:bend:pivot` (`float3`) | bounds bottom-centre | World-space point to bend around. Give parts that bend together (a jug and its separate handle) the same pivot, or they come apart. |

All of it happens in the camera's view, around a pivot: `rostrum:bend:pivot` if set, otherwise the **bottom-centre of the mesh's world-space bounding box**. See `looks/shot-bend.usda` for a working shot layer. The bend also moves the shadow casters, so shadows follow the bent shape. Lighting uses the original, un-bent normals. Because the bend is tied to a camera path, the same mesh can look different from two cameras in the same scene.

## 6. Renderer settings — authored on `/RostrumLook`

Name = `rostrum:<group>:<name>`. In the shader the name is `u_<group>_<name>` (colons become underscores). A colour is a `color3f` attribute, which is sent as three settings `…:x`, `…:y`, `…:z` (shader `u_ink_color_x/y/z`). Numbers, ints and bools are accepted; other types give a warning.

| Setting | Default | What it does |
|---|---|---|
| `rostrum:ss` | 2 | Supersampling: renders at this multiple of the size (1–4, whole number) and reduces. Higher = smoother lines, slower, more video memory. |
| `rostrum:shadow:size` | 4096 | Shadow-map size in pixels (one square map per shadowed light). Re-created when it changes. |
| `rostrum:shadow:soft` | 1.5 | Shadow edge softness, in shadow-map texels (a 5×5 blur). |
| `rostrum:shadow:offset` | 0.15 | Pushes the shadow lookup off the surface, in scene units. Raise if surfaces shadow themselves (speckle); lower if shadows detach from objects. |
| `rostrum:bg:color` | (0, 0, 0) | Colour where nothing is drawn. |
| `rostrum:brush:amount` | 0 | Strength of brush strokes on the lighting (section 4.2). 0 = off. |
| `rostrum:brush:length` | 18 | Stroke length, output pixels. |
| `rostrum:brush:width` | 3 | Stroke width, output pixels. |
| `rostrum:brush:angle` | 35 | Fixed stroke angle on screen, degrees. |
| `rostrum:brush:follow` | 0.7 | 0 = strokes all at the angle; 1 = follow the form. |
| `rostrum:ink:width` | 1.6 | Line width, output pixels. 0 = no ink at all. |
| `rostrum:ink:crease` | 0.6 | Crease-line width relative to silhouettes. |
| `rostrum:ink:creaseAngle` | 35 | Degrees between neighbouring normals where a crease reaches full width. |
| `rostrum:ink:creaseSoft` | 15 | Degrees over which a crease fades in (below `creaseAngle − creaseSoft` nothing). |
| `rostrum:ink:depthJump` | 0.05 | Relative depth step between neighbours that counts as an edge (a fold in front of something else). |
| `rostrum:ink:lightTaper` | 0.6 | How much lines thin out where the surface is well lit (0 = no change; 1 = vanish in full light). |
| `rostrum:ink:depthTaper` | 0.4 | How much lines thin out with distance from the camera (nearest to farthest object). |
| `rostrum:ink:wobble` | 0.4 | How much the width varies along a line. 0 = even. |
| `rostrum:ink:wobbleScale` | 40 | Size of that variation, output pixels. |
| `rostrum:ink:opacity` | 0.9 | How strongly lines cover the picture (0–1). |
| `rostrum:ink:color` | (0.04, 0.03, 0.05) | The ink colour. |
| `rostrum:ink:albedoMix` | 0.5 | 0 = pure ink colour; 1 = a darker version of the surface colour under the line. |
| `rostrum:ink:albedoDark` | 0.3 | How dark that surface-coloured line is (multiplier on the surface colour). |
| `rostrum:paper:amount` | 0 | Paper/canvas grain strength (multiplies the picture by `1 + amount × grain`). 0 = off. |
| `rostrum:paper:scale` | 1.5 | Grain size, output pixels. |

## 7. How ink width is made and drawn

**Measured per pixel (`edges.frag`)**, in a supersampled frame:
1. A pixel is on a **silhouette/fold** if a neighbour is another object or background, or the same object but much farther away (`depthJump`). Only the nearer side gets the line.
2. It is on a **crease** if the surface normal changes against the neighbour one output-pixel away; a smoothstep from `creaseAngle − creaseSoft` to `creaseAngle` gives 0..1.
3. Width = the larger of (silhouette = 1) and (crease × `ink:crease`), times `ink:width`.
4. Thinned in light: `× (1 − lightTaper × smoothstep(0.25, 1, howLit))`, where howLit is the average lit value of that pixel (lights weighted by their brightness).
5. Thinned with distance: `× (1 − depthTaper × (distance 0..1 between the nearest and farthest drawn thing))`.
6. Varied by a slow noise: `× (1 + wobble × noise × 1.6)`, never below 0. Where the width goes to zero a line ends, which is why lines taper and break.

Unlit "card" surfaces (as painted) and the background get no ink.

**Drawn (`ink.frag`)**: each edge pixel becomes a round dot of its own width; the line is the union of those dots. The colour is `mix(ink:color, albedo × albedoDark, albedoMix)`, laid over the shaded picture by `ink:opacity`. Paper grain comes last. The search radius for dots is capped at 12 supersampled pixels, so very wide lines get clipped.

## 8. How to render

Through the GPU slot (`render.ps1` asks for the NVIDIA chip and records video memory):

```
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "<team>: <what>" gpu pwsh -NoProfile -File C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-stylized\render.ps1 <stage.usda> <out.png> --look <layer.usda> [--width 1920 --height 1080] [--camera /World/Cam]
```

Writes `<out.png>` and `<out>.stats.json` (settings used, time, memory). `--camera` picks the camera; without it the first camera in the stage is used, and it is also the path `rostrum:bend:camera` is compared with. Any Hydra/USD error stops the run with a non-zero exit and no image. `--frames N` times extra frames. `--renderer storm|cycles` renders the same stage with another delegate, to compare.

## 9. Compare looks side by side

```
uv run --with pillow python -I compose.py out.png a.png "Label A" b.png "Label B" [c.png "Label C" ...] [--height 540]
```

Each image is scaled to the height, with a label under it. A missing file stops it with a message.

## 10. Known limits

- At most **8 lights**; any beyond are ignored with a warning. At most **4 shadowed** lights; later ones render without shadow.
- Rect and disk lights act as a point light with one facing side; no area softness, no size.
- Sphere/point lights have no distance falloff. `intensity` and `exposure` are not read (use `rostrum:gain`).
- The bend lights with the **un-bent** normals; bend only matters on the picture's outline and shadows.
- No transparency or refraction. Textures: 8-bit only.
- Dome lights give a flat hemisphere term; no environment texture is sampled.
