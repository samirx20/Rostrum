# Rostrum3D document (`.trd`)

*Team Hem, H12, 2026-10-21. Code: `apps/3d/python/rostrum3d/`. The fields of every type, their ranges, defaults, `valid_when` and importance: `rostrum3d/fields.py` (the one table).*

```
doc ─ items     ─ group  ─ children (items) ─ keys
                ─ import ─ children (items), parts ─ keys      (a USD file by reference; parts = overrides on prims inside it)
                ─ rig    ─ children (items) ─ keys      (a camera rig: orbit / crane / dolly, handheld)
                ─ mesh | light | camera ─ keys
    ─ materials ─ material
    ─ shots     ─ shot
```

- **Units:** metres, Y up, degrees, seconds. Colours are `#rrggbb` (sRGB); the compiler makes them linear.
- **Transform on every item:** `x y z rx ry rz sx sy sz visible`, relative to the parent; rotation is applied X, then Y, then Z (USD `rotateXYZ`).
- **Aim:** `aim` = `none` | `point` (`aimX aimY aimZ`) | `item` (`aimItem`). The compiler turns it into `rx ry rz` every frame so the item's −Z (where cameras and rect/disk lights face) points at the target, Y as close to up as it goes, no roll. While aimed, `rx ry rz` are not shown or accepted (rule of individuality).
- **Rigs (H21):** a `rig` holds the camera (or anything); `rig` = `orbit` (`radius height angle`, head faces the centre) | `crane` (`armLength lift swing`, level head) | `dolly` (`travel` forward along −Z); every rig has `pan tilt` and a seeded `handheld` drift (`shake shakeFrequency shakeMove seed`). Its own `x y z rx ry rz` are the base (no aim, no scale). The compiler (`rostrum3d/rigs.py`) turns it into a group with its transform baked per frame, Euler angles kept continuous; the core never sees a rig. How-to: `guides/camera-rigs.md`.
- **Mesh shapes:** `box sphere cylinder plane disc torus`, and three flat outlines the core extrudes `depth` deep (with `bevel`, `segments`, `smooth`; the faces can take their own materials: `frontMaterial bevelMaterial sideMaterial backMaterial`, `""` = the mesh's `material`, bevel `""` = front's): **`text`** (`text font weight size tracking lineHeight align`; font = Inter, Recursive, RobotoFlex or an absolute .ttf/.otf; `size` is the em in metres; `tracking` in thousandths of an em), **`svg`** (`svgFile` or `pathData`, `svgWidth`), **`path2d`** (`doc2d` = a 2D item id in the same project folder, `layer` = a path layer id in it, `svgWidth`). The outline is centred on the item origin (text: horizontally per `align`, vertically capital-height to last baseline; drawings: their ink's middle), so the item spins around its middle. `rostrum3d/outline*.py` make the outlines (HarfBuzz shaping, skia-pathops merge, flattened to ~0.1 mm or 0.2 % of the size); the compiler sends them as mesh shape `"outline"` and drops the document-only fields. Drawings: filled shapes only, `fill="none"` skipped, a white shape on top is another filled shape, not a hole.
- **Keys:** the 2D key model (`t` seconds, `v` or `c`, `ease`), ids `<item>.<field>.k<ms>`; evaluator, easing table and the four key operations are `rostrum_core.keys`. Animatable: every number and colour field of an item, except a mesh's shape sizes (the core builds a mesh once). Materials and shots don't animate in v1.
- **Shots:** `camera` (a camera's id), `fps`, `start`, `end` **in seconds**, `width`, `height`, `background`. Frames run from `round(start × fps)` to `round(end × fps) − 1` (a 2 s shot at 24 fps = frames 0..47); frame *n* is at *n* / fps seconds.
- **Ids:** items and materials become USD prim names, so letters, digits and `_` only. Parts are `<import>.<path with _>`; keys come from their content.
- **References are checked** after every change: a mesh/import/part's `material`, a shot's `camera`, an aim's `aimItem` must name a real thing of that type. Deleting a material clears it from its users in the same step; deleting a camera a shot uses is refused until the shot names another.

## Public API (what the engine client and MCP server use)

- `rostrum3d.kind.KIND` (also `rostrum3d.KIND`), `REGISTRY`: the document kind and its operations.
- `rostrum3d.compile.describe(data, shot_id)` → the scene (ENGINE_CONTRACT.md § 2).
- `rostrum3d.compile.shot_info(data, shot_id)` → `{id, camera, fps, start, end, width, height}`; `start`/`end` are **frames** (inclusive).
- `rostrum3d.script.run_source(source, name)` → a tree for `doc.run_script(name, tree)`.

Operations: `group.add mesh.add light.add camera.add rig.add import.add part.add material.add shot.add`, `item.remove item.rename item.arrange item.aim`, `material.assign material.remove shot.remove`, `key.add key.remove key.clear value.set`, and one `<type>.set` per type (`mesh.set`, `light.set`, `camera.set`, `material.set`, `shot.set`, `part.set`, `key.set` …).
