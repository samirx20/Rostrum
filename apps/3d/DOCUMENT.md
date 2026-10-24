# Rostrum3D document (`.trd`)

*Team Hem, H12, 2026-10-21. Code: `apps/3d/python/rostrum3d/`. The fields of every type, their ranges, defaults, `valid_when` and importance: `rostrum3d/fields.py` (the one table).*

```
doc ─ items     ─ group  ─ children (items) ─ keys
                ─ import ─ children (items), parts ─ keys      (a USD file by reference; parts = overrides on prims inside it)
                ─ rig    ─ children (items) ─ keys      (a camera rig: orbit / crane / dolly, handheld)
                ─ mesh ─ bones (bone ─ bones … ─ keys) ─ keys      (a bone chain, each bone inside the one before)
                ─ light | camera ─ keys
    ─ materials ─ material
    ─ shots     ─ shot
    ─ poses     ─ pose
```

- **Units:** metres, Y up, degrees, seconds. Colours are `#rrggbb` (sRGB); the compiler makes them linear.
- **Transform on every item:** `x y z rx ry rz sx sy sz visible`, relative to the parent; rotation is applied X, then Y, then Z (USD `rotateXYZ`).
- **Aim:** `aim` = `none` | `point` (`aimX aimY aimZ`) | `item` (`aimItem`). The compiler turns it into `rx ry rz` every frame so the item's −Z (where cameras and rect/disk lights face) points at the target, Y as close to up as it goes, no roll. While aimed, `rx ry rz` are not shown or accepted (rule of individuality).
- **Rigs (H21):** a `rig` holds the camera (or anything); `rig` = `orbit` (`radius height angle`, head faces the centre) | `crane` (`armLength lift swing`, level head) | `dolly` (`travel` forward along −Z); every rig has `pan tilt` and a seeded `handheld` drift (`shake shakeFrequency shakeMove seed`). Its own `x y z rx ry rz` are the base (no aim, no scale). The compiler (`rostrum3d/rigs.py`) turns it into a group with its transform baked per frame, Euler angles kept continuous; the core never sees a rig. How-to: `guides/camera-rigs.md`.
- **Mesh shapes:** `box sphere cylinder cone capsule plane disc torus` (cone and capsule: `radius height`), and three flat outlines the core extrudes `depth` deep (with `bevel`, `segments`, `smooth`; the faces can take their own materials: `frontMaterial bevelMaterial sideMaterial backMaterial`, `""` = the mesh's `material`, bevel `""` = front's): **`text`** (`text font weight size tracking lineHeight align`; font = Inter, Recursive, RobotoFlex or an absolute .ttf/.otf; `size` is the em in metres; `tracking` in thousandths of an em), **`svg`** (`svgFile` or `pathData`, `svgWidth`), **`path2d`** (`doc2d` = a 2D item id in the same project folder, `layer` = a path layer id in it, `svgWidth`). The outline is centred on the item origin (text: horizontally per `align`, vertically capital-height to last baseline; drawings: their ink's middle), so the item spins around its middle. `rostrum3d/outline*.py` make the outlines (HarfBuzz shaping, skia-pathops merge, flattened to ~0.1 mm or 0.2 % of the size); the compiler sends them as mesh shape `"outline"` and drops the document-only fields. Drawings: filled shapes only, `fill="none"` skipped, a white shape on top is another filled shape, not a hole.
- **Keys:** the 2D key model (`t` seconds, `v` or `c`, `ease`), ids `<item>.<field>.k<ms>`; evaluator, easing table and the four key operations are `rostrum_core.keys`. Animatable: every number and colour field of an item, except a mesh's shape sizes (the core builds a mesh once). Materials and shots don't animate in v1.
- **Timing (brief 17):** `timing` on every item that has a transform (not rigs, not domes) = `smooth` (default) | `on2` | `on3`. On n, every value is held for n frames: frame f shows the values of frame `start + ⌊(f − start) / n⌋ · n` (counted from the shot's first frame), aims and pivots included. An item's own `on2` / `on3` wins; `smooth` follows its nearest group's. The compiler does the holding (`compile._Frames.values`), so the viewport and the render (both `compile.describe`) step alike; the core never sees `timing`. Shown (`valid_when` fact `animated`) only once the item or something inside it has keys; a script may give it before its keys.
- **Bones (brief 19):** a mesh's `bones` list holds its chain, each `bone` `{x y z (head, in its parent's space: the mesh's own space for the first, else the bone before it), rx ry rz (Turn, the only keyable fields), length, bones, keys}`; a bone runs along its own +Y from its head, so the next bone's head is `(0, length, 0)`. The mesh's `skinned` (Bend with bones, shown when it has bones: fact `boned`) is never sent; the compiler sends the chain only as the mesh node's `skin` (ENGINE_CONTRACT.md § 2, `rostrum3d/skin.py`): rest heads and tails, and per frame each bone's move from rest. Made by `bone.chain` (points → bones, one step), `bone.bind` (off / on). `rostrum3d/ops_bones.py`.
- **Poses (brief 17):** doc-level `poses`, each `{id, type: "pose", name, fields: ["lid.rx", …], values: [−105, …]}` (field `<item id>.<field>`, one number each). Made by `pose.save` (x y z, rx ry rz unless aimed, sx sy sz of each target at a time), keyed back by `pose.apply` (at a time; `share` 0..1 = a breakdown between the neighbouring keys); `pose.rename`, `pose.remove`. Items deleted later are skipped on apply and named. `rostrum3d/ops_poses.py`.
- **Shots:** `camera` (a camera's id), `fps`, `start`, `end` **in seconds**, `width`, `height`, `background`. Frames run from `round(start × fps)` to `round(end × fps) − 1` (a 2 s shot at 24 fps = frames 0..47); frame *n* is at *n* / fps seconds.
- **Ids:** items and materials become USD prim names, so letters, digits and `_` only. Parts are `<import>.<path with _>`; keys come from their content.
- **References are checked** after every change: a mesh/import/part's `material`, a shot's `camera`, an aim's `aimItem` must name a real thing of that type. Deleting a material clears it from its users in the same step; deleting a camera a shot uses is refused until the shot names another.

## Public API (what the engine client and MCP server use)

- `rostrum3d.kind.KIND` (also `rostrum3d.KIND`), `REGISTRY`: the document kind and its operations.
- `rostrum3d.compile.describe(data, shot_id)` → the scene (ENGINE_CONTRACT.md § 2).
- `rostrum3d.compile.shot_info(data, shot_id)` → `{id, camera, fps, start, end, width, height}`; `start`/`end` are **frames** (inclusive).
- `rostrum3d.script.run_source(source, name)` → a tree for `doc.run_script(name, tree)`.

Operations: `group.add mesh.add light.add camera.add rig.add import.add part.add material.add shot.add`, `item.remove item.rename item.arrange item.aim`, `material.assign material.remove shot.remove`, `key.add key.remove key.clear value.set`, and one `<type>.set` per type (`mesh.set`, `light.set`, `camera.set`, `material.set`, `shot.set`, `part.set`, `key.set` …).
