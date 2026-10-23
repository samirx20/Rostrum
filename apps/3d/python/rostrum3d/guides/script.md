# The 3D script: `run_script` on one page

A script is Python that describes the scene. `run_script` runs it, checks the whole result, and merges it into the document, so
running it again changes only what the script now says differently and leaves what a person moved. The script never touches the
engine or a USD file; the same fields work in `edit_document` (`mesh.set`, `light.add` …).

## The shape of a script

```python
m = material("steel", baseColor="#c9ccd1", metallic=1, roughness=0.3)
cube = mesh("cube", shape="box", width=0.1, height=0.1, depth=0.1, material=m)
cube.key("ry", {0: 0, 2: (90, "linear")})
light("key", kind="rect", width=0.5, height=0.4, intensity=5, x=1, y=1, z=1).aim(cube)
cam = camera("cam", focalLength=85, z=1).aim((0, 0, 0))
shot("main", camera=cam, fps=24, start=0, end=2)
```

Each helper returns a handle. Pass a handle (or its id as text) wherever a field names another thing.

## Helpers

| Helper | Makes |
|---|---|
| `group(id, **fields)` | a group; items made inside `with group(...):` go in it |
| `mesh(id, shape=, **fields)` | `box sphere cylinder plane disc torus`, or the outlines `text svg path2d` |
| `light(id, kind=, **fields)` | `rect disk strip sphere distant dome` |
| `camera(id, **fields)` | a camera (looks along its −Z, Y up) |
| `rig(id, rig=, **fields)` | a camera rig: `orbit crane dolly` (a holder: `with rig(...):`) |
| `import_usd(id, file=, parts=[…], **fields)` | a USD file by reference (also a holder) |
| `material(id, **fields)` | a material (lists at the top level, not in a group) |
| `shot(id, camera=, fps=, start=, end=, width=, height=, background=)` | a shot |

Every argument besides `id` is a field. The field names, ranges and defaults are the ones `inspect_operations` (the `<type>.add` / `<type>.set` entries) and `inspect_item` show; an unknown field, a wrong type or an out-of-range number fails (see Errors). Units: metres, degrees, seconds;
colours `"#rrggbb"`.

A field that doesn't apply as the item is made is refused, never stored: `width` on a sphere, `fStop` without `dof=True`, a
`strip`'s `length` on a `rect`. Set what it depends on in the same call (`shape=`, `kind=`, `dof=True`, `rig=`).

The fields, by item (all items also take `x y z rx ry rz sx sy sz visible`; a rig takes only `x y z rx ry rz visible`):

- **mesh** `shape width height depth radius tube bevel segments smooth material`; text: `text font size weight tracking lineHeight align`;
  svg: `svgFile` or `pathData`, `svgWidth`; path2d: `doc2d layer svgWidth`; outline faces: `frontMaterial bevelMaterial sideMaterial backMaterial`
  (`depth` is how far an outline is pushed out).
- **light** `kind length width height radius angle texture turn seenByCamera color intensity exposure temperature spread card lightsOnly normalize shadows`
  (`lightsOnly` is ids separated by spaces; `turn` and `texture` are for a dome).
- **camera** `focalLength sensorWidth dof fStop focusDistance near far`.
- **rig** `rig radius height angle armLength lift swing travel pan tilt handheld shake shakeFrequency shakeMove seed`.
- **material** `baseColor baseColorTexture metallic roughness roughnessTexture transmission ior coat coatRoughness anisotropy anisotropyRotation bumpTexture bumpStrength emissionColor emissionStrength thinFilm`.
- **import** `file prim material`; **part** `path material visible`.
- **shot** `camera fps start end width height background`; its render settings `renderQuality renderSamples renderDenoise renderSize renderRange renderStart renderEnd`
  (`inspect_guide` `agents`, "Render settings and the time estimate").
- Every item also takes `name="…"` (what screens show). Left out, the name is the id.
- A plane lies flat, facing up: `width` (along X) × `depth` (along Z); it has no `height`.
- `lightsOnly` takes a handle, a list of handles / ids (`lightsOnly=[device, "floor"]`), or ids separated by spaces.

More on lights, materials and rigs: `inspect_guide` `lighting`, `materials`, `camera-rigs`.

## Ids and re-runs

- The first argument is the id: letters, digits and `_`, not starting with a digit (ids become USD names). Left out, it is counted per type
  (`mesh_1`, `mesh_2` …), skipping every quoted word in the script, so adding one item never renames another. Name anything you
  will refer to later, move, or key; counted ids are fine for repeated filler.
- An id is used once in a script, across all kinds (a mesh and a light can't both be `top`).
- **The same id is the same thing next run.** The merge compares what the script made last time with what it makes now and with
  the document as it is. A value a person (or another script, or `edit_document`) changed since is kept, and `run_script` lists it as
  *held back* with who changed it. To make the script win, run again with `force: ["key.x"]` (those keys) or `force: true` (all).
- Items and keys the script no longer makes are removed; things a person added themselves are left alone.
- Give a script a stable `name` (`run_script`'s `name`, default `agent_script.py`) and re-run under it to merge. A different name is a different script.
- Don't change an id's kind between runs (`mesh("a")` then `light("a")`): use a new id. If a person had edited the old item, the run is
  refused, naming the fields the new kind doesn't have; if nobody had, the item is rewritten in place as the new kind.

## Nesting

```python
with group("device", ry=-12) as device:
    mesh("body", shape="box", width=0.07, height=0.02, depth=0.1)
    with rig("spin", rig="orbit", radius=0.5):
        camera("cam")
with import_usd("phone", file=r"C:/assets/phone.usdc", parts=["Body/Screen"]) as phone:
    phone.part("Body/Frame", material=steel)       # material= and visible= on a prim inside the file
```

Only a group, a rig or an import holds items. `with` on anything else is an error. An item's transform is relative to its holder.
Materials and shots always go to the top level, even when made inside a `with`.

## Handle methods

- `item.set(**fields)` changes fields after the item was made. Returns the handle.
- `item.key(field, {seconds: value}, ease="smooth")` animates a number or colour field. A value can be `(value, "ease")` to
  give that one stretch its own ease. Colour fields take `"#rrggbb"` values. Call it again with another field to key more.
  Returns the handle, so `.key(...).key(...)` chains.
  Animatable: every number or colour field except a mesh's shape fields, a light's `spread`, and `aim`. A key's ease shapes the stretch
  that starts at it. Eases: `linear hold smooth snappy natural heavy easeIn easeOut easeInOut spring bounce custom`.
  Key ids come from the item, field and time (`cube.ry.k2000`), so the same script gives the same keys every run.
  Springs and curves: `item.key("y", {0: 0.1, 1: 0}, ease="spring", stiffness=240, damping=14)` (settings on every key), or per key
  `{0: {"v": 0, "ease": "custom", "x1": 0.2, "y1": 0, "x2": 0.1, "y2": 1.1}, 1: 30}`. A setting that doesn't fit the key's ease is refused.
- `item.aim(item_or_id)` or `item.aim((x, y, z))` points the item's −Z at an item's origin or a point, every frame (turns `rx ry rz` off while it aims).
  `item.aim(target, roll=90)` then turns it around the way it points: a strip light stands on end, a camera's horizon tilts. `roll` can be keyed.
- `import.part(path, **fields)` an override on a prim inside an import's file (paths from `inspect_usd_file`).

## Inside the script

Python as usual (loops, functions, f-strings, `math`). Available: `range len min max abs round enumerate zip list dict tuple float int str sorted reversed sum isinstance`
and `import math`. Nothing else: no files, no other imports, no `print`. A script can't read the document, so it can't base a value on what a person did.

## Errors

A script that fails changes nothing. The error names the script and line, then what was wrong and what is accepted:

- `script "p.py" failed (line 4): … "wd" is not a field of a mesh. Accepted: shape, width, …` (a near miss gets a suggestion)
- `… a.width only applies when shape is 'box' or shape is 'plane'. Set that too to use width.`
- `… a.ry at 1 s: ease='bogus' is not one of the choices. Accepted: linear, hold, …`
- `… "width" can't be animated on a camera; animatable: focalLength, …`
- `… id "a" is used twice in the script (already mesh).`
- `… cube is a mesh; only a group or an import holds items.`
- After the script runs, the whole document is checked: `the merged document would break its check: s.camera: no camera "nope" (there are: …)`
  (a missing material, a shot camera that isn't a camera, a shot that ends before it starts, an aim at itself). Still nothing is merged.

In `edit_document`, a taken id is refused naming what holds it: `id "top" is already used by a mesh`.

## What a script can't do (use `edit_document`)

- Delete or move anything by hand (`item.remove`, `item.arrange`), duplicate (`item.duplicate`), rename (`item.rename`), or stop an aim (`item.aim off`): a script only describes what should exist.
- Change a key on something it didn't make, or change a single key's time, value or ease afterwards (`key.set`, `key.remove`, `key.clear`, `value.set`).
- Shape a key's curve: `custom` ease points and `spring` stiffness / damping are key fields only `key.set` reaches (a script's `spring` / `custom` use the defaults).
- Add a part to an import it didn't make, or anything to the document's own settings.
- Use markers: shot and key times in a script are plain seconds.
- Look at anything. After each run use `look_frame`, `look_sheet` and `look_at`.
