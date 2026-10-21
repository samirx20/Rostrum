# P-3D-1 scene: product close-up

Regenerate: `python -I make_scene.py` (stdlib only) → `product.usda` (~2 MB ASCII, ~28k points, 11 meshes).
All tweakable values are at the top of `make_scene.py`: sizes, `MATERIALS`, `CAMERA`, `FOCUS_ON`, `LIGHTS`.

## Design (our own object)
A chunky palm-sized slab (7.4 × 9.8 × 1.7 cm) with a big lens dial on top:
- **Body**: rounded-rectangle anodized aluminium (graphite), rounded bottom edge, **polished 45° chamfer** around the top edge (separate mesh so it gets its own mirror-bright material).
- **Top glass**: 1.4 mm closed glass slab with a half-round edge, over a black "ink" layer (glass over black gives reflections with depth).
- **Dial**: steel ring with **120 machined knurl ridges** on its outer wall (geometry, not a texture), polished top face with chamfers in and out.
- **Lens**: plano-convex sapphire-index (1.77) dome with a thin-film coating (280 nm), over a black floor and a small iridescent "sensor" disc (thin film 520 nm on dark metal).
- **Side button**: small polished capsule on the right wall.
- **Backdrop**: dark seamless cyc (floor → 35 cm curve → wall), slightly glossy so the device sits on a soft reflection.

Every mesh has per-vertex normals (`interpolation = "vertex"`), `subdivisionScheme = "none"` (the delegate ignores authored normals on subdivided meshes), and face winding that agrees with the normals (checked: 0 mismatches; closed parts have positive volume). Hard edges are separate vertex rings, not shared vertices.

## Materials
Each `Material` has two outputs:
- `outputs:cycles:surface` → a `cycles_principled_bsdf` shader, connected from `outputs:BSDF` (the delegate prefers the `cycles` network and uses the upstream output name as-is for native nodes, so it must be exactly `BSDF`).
- `outputs:surface` → a `UsdPreviewSurface` fallback, so usdview and other renderers show something sensible.

Socket names come from `src/scene/shader_nodes.cpp` (`base_color`, `metallic`, `roughness`, `ior`, `transmission_weight`, `thin_film_thickness`, `thin_film_ior`, ...). **MaterialX is not converted by this delegate**, so don't author MaterialX networks for Cycles.

**No anisotropic (brushed) metal**: principled anisotropy with no tangent input falls back to the "generated" coordinates, which the Hydra mesh path does not seem to provide. A brushed look needs UVs + a tangent node; left out for this proof.

## Lights (UsdLux, intensity = surface brightness, `normalize` off)
| Light | Role |
|---|---|
| KeyTop 70×45 | big softbox overhead-behind: soft gradients on the dial top and body |
| StripLeft / StripRight 8×90 | tall strips behind left/right: long hot lines on the chamfer, knurl and lens rim |
| FrontFill 60×20 | very weak cool card in front, lifts the dark sides |
| WallGlow 80×30 | aimed at the backdrop curve: the top glass reflects this glow (camera's mirror direction lands on that wall) |
| Ambient (dome) 0.02 | keeps pure-black reflections from being dead |

Rect lights face their local −Z; `look_at()` aims them. Colour temperatures 4800–7000 K.

## Camera
`/World/HeroCamera` (the only camera; the delegate uses the first `UsdGeomCamera` it finds — it does **not** read UsdRender settings). 100 mm, 36 × 20.25 mm sensor (16:9), **f/4**, focus on the dial bezel edge nearest the camera (computed automatically, ~35 cm). Depth of field at this distance is only a few mm: the near bezel is sharp, the back of the device falls off. Raise `fstop` (5.6–8) if too much is soft.

## What to tweak after the first render
- Too dark/bright overall: change all `LIGHTS` intensities together (or add exposure in the render).
- Chamfer lines missing: move `StripLeft`/`StripRight` along X/Z; highlights on a mirror edge only show where the light sits in the mirror direction.
- Glass top looks flat black: raise `WallGlow` or move it so the wall patch the glass reflects is brighter.
- Different look: `MATERIALS["Anodized"]["base_color"]`, `YAW_DEG`, `CAMERA`.

## Unsure about (check on the first render)
1. **Image shape**: the standalone app conforms the camera to the camera's size at the moment the file is read (Cycles default 1024×512), and only afterwards applies `--width/--height`. A 16:9 render might come out horizontally squeezed/stretched. If so, fix it in the app (set the size before reading), not in the stage.
2. The `outputs:cycles:surface` terminal relies on UsdImaging building a separate `cycles` network context; if that context isn't produced, the universal network (UsdPreviewSurface) is used and you lose thin film / transmission control (glass becomes opacity-based). Look for "Could not create node" or "Could not find terminal output" warnings.
3. Light intensity numbers are first guesses (no render was run).
