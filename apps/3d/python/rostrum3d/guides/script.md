# The 3D script: `run_script` on one page

A script is Python that describes the scene. `run_script` runs it, checks the whole result, and merges it into the document, so
running it again changes only what the script now says differently and leaves what a person moved. The script never touches a USD
file (only posing a clay asks the engine to measure its shape); the same fields work in `edit_document` (`mesh.set`, `light.add` …).

## The way to work: one script, look, edit, re-run

1. Write the **whole scene** as one script (`run_script` with `path` to a .py file you keep, or `source` + a `name`).
2. Look (`look_frame` is the main check: a quick frame in seconds; `what "sheet"` for the whole shot) and judge it yourself.
   `notes: true` on a look or render adds measured notes, if you want them.
3. Edit **that same script** (the whole text, with your change) and run it again under **the same name**. It replaces what
   it made: changed values change, keys are rewritten, things you deleted from the script go (the reply lists them; `edit_undo`
   brings them back). What a person changed by hand is kept and listed as held back.

A re-run that leaves out most of what its last run made (2 or more things, more than half) still runs, and the reply warns
which things it removed (`edit_undo` brings them back). For a small change on its own, use a **new** name and
`edit("ball", y=0.3)`; to take things out on purpose, `remove("wall", "ball")`.

## A character: one clay, posed by its joints

A figure is **one clay**: body, head, arms and feet are pieces of it, so it holds together and its joints are found
from its shape. Not separate meshes in groups (they drift apart and need moving together by hand).

```python
c = clay("buddy", radius=0.07)                         # a ball: its middle at (0, 0.07, 0); legs below lift it to stand
c.lump((0, 0.175, 0), 0.055, name="head", blend=0.012) # every position: x, HEIGHT ABOVE THE GROUND, z
c.lump((0.06, 0.095, 0), 0.02, to=(0.17, 0.02, 0), name="arm")   # held a little out; Mirror makes the other side
c.lump((0.035, 0.015, 0), 0.026, to=(0.04, -0.04, 0), name="leg")             # legs read as legs, not blobs under a ball
c.lump((0.042, -0.048, 0.012), 0.02, to=(0.045, -0.05, 0.045), name="foot")   # a foot pointing forward, flat on the floor
# A blend joins only what a piece touches, decided per pair: the arm joins the body as softly as asked, and eases off
# near the head it doesn't touch, so a raised arm comes away from the head cleanly without a crease at the body.
# a wave that reads on camera: the hand goes up BESIDE the head, a little in front of it (never over its middle), and
# swings side to side by a good share of the figure's height (here ~12 cm), three swings and more, until the shot ends;
# the other arm hangs relaxed. A 2 cm move reads as still. Turning points every 0.35 s, not 0.5 or 1 s: stills one
# second apart would catch the same pose.
c.pose(0, **{"picture-right hand": {"up": 0.06, "out": 0.02}, "picture-left hand": {"up": -0.03, "out": 0.01}})  # a real move: 0 m keys nothing
c.pose(0.4, **{"picture-right hand": {"up": 0.14, "out": -0.03, "forward": 0.05}})       # the lift
for i in range(8):                                                                      # a swing every 0.35 s to the end
    c.pose(0.8 + 0.35 * i, **{"picture-right hand": {"up": 0.17, "out": -0.11, "forward": 0.06} if i % 2 == 0  # in, by the head
                              else {"up": 0.12, "out": 0, "forward": 0.06}})                             # out to the side
# c.bend("arm.R", {0: (0, 0, 0), 1: (0, 0, -80)})   # instead of pose: one joint by degrees about the clay's X, Y, Z from rest
mesh("eye", shape="sphere", radius=0.0085, x=0.02, y=0.182, z=0.047, attach_to=c)    # rides the head's bone
mesh("eye2", shape="sphere", radius=0.0085, x=-0.02, y=0.182, z=0.047, attach_to=c)  # its pair: same size, same height
```

**Positions.** `clay(id, radius=r)` without `at` / `y` puts the clay's origin on the ground under the ball, so its own
space is the scene's: every `.lump` / `.stroke` / `.draw` position, `attach_to` part and `pose` point is (x, height above
the ground, z). A piece reaching below the ground lifts the whole figure (and what is attached) to stand on it. With
`at=` (or `y=`) the clay's origin is there instead, and its pieces are measured from that point.

Pose after the last piece (the first `bend` / `pose` finds the joints from the shape so far; a piece added after is made, its
joints stay as found, shown as out of date, and the reply says so). Names: `body`,
`chest`, `head`, `arm.R`, `forearm.R`, `hand.R` (the arm's end), `foot.L` …; `.R` is the −x side; in words `"right
hand"`, or `"picture-left hand"` (the one on the picture's left); a wrong name fails listing the ones found. `holds` takes joint names: holding `"body"` keeps the whole trunk upright (the head still
turns), holding the feet keeps them planted. Guide `posing`.

## Ground first, place by relation, frame by subject

**Changed: `y` is now height above the ground.** A mesh, import, group or combine made directly in the scene stands
on the ground: its `y` is the height of its **base** (its lowest point at rest, as turned and scaled) above the
ground's top, so no `y=h/2` by hand; `y=0.3` lifts its base 30 cm; y keys mean the same. `y_world=` puts its own
origin (a shape's middle, an import's base) at that world height instead: the rare floating thing. A group stands on
the ground as a whole; what is inside a group keeps the group's space. Falling things too: `y` = how high their base
starts. Lights, cameras, the ground itself and `attach_to` parts are as before.

```python
table = mesh("table", shape="box", width=1, height=0.05, depth=0.6, y=0.7)  # its base 70 cm up
mug = mesh("mug", shape="cylinder", radius=0.04, height=0.1).place_on(table)      # on its top, over its middle
mesh("jar", shape="cylinder", radius=0.05, height=0.14).place_on(mug, beside="right", gap=0.03)
row([mesh("a", shape="sphere", radius=0.05), mesh("b", shape="box", width=0.1, height=0.1, depth=0.1)], gap=0.05)
cam = camera("cam", focalLength=50).take_view((0, 1.2, 2.2), table)   # stand here, aim at that
shot("hero", camera=cam, end=4, frame=mug, at=(1/3, 0.5), fill=0.5)   # the mug's middle on the left third
item("hero").key("frame", {0: {"fill": 0.3}, 4: {"fill": 0.6}})       # a push-in: ordinary x y z keys on cam
```

Sides are the world's (left = −X, right = +X, front = +Z towards the start camera, back = −Z), by the things' real boxes,
turned or in groups. `frame=` keeps the camera's direction and lens (an aimed camera keeps the turn it has and stops
aiming) and moves it: `at` = where the subject's middle lands (fractions from the picture's left and top), `fill` = its
share of the picture's height.

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
| `mesh(id, shape=, **fields)` | `box sphere cylinder cone capsule plane disc torus`, or the outlines `text svg path2d` |
| `item.place_on(other, gap=)` | its base on the other's top, over its middle (by real boxes: turned, in groups) |
| `item.place_on(other, beside="left"\|"right"\|"front"\|"back", gap=)` / `place_on(in_front_of=other)` | next to it on that world side, lined up with its middle, its base level with its base, `gap` metres between |
| `row([a, b, c], gap=0.1, centre=True, axis="x", at=)` | side by side in that order, the row's middle on 0 (or `at`), all on the ground |
| `cam.take_view(pos, look_at)` | the camera stands at `pos` and aims at `look_at` (a point or an item) |
| `shot(id, camera=, frame=item_or_list, at=(x, y), fill=)` / `shot.key("frame", {t: {"fill": …}})` | frame the subject: its middle at `at` (picture fractions from left / top), its height `fill` of the picture; keyed = a push-in. Any item: an import is measured from its file |
| `item.place_on(clay or mesh, at=(x, y, z), normal=)` | stand a mesh on that surface at a world point (`normal` left out: straight out from its upright middle line); on a clay with Mirror on, off its middle (farther than its own half size), it also gets its mirrored copy `<id>_mirrored`, which follows it; on a clay it also follows the clay's pose (`follow=<clay>`, `followPose=True`). From a pixel of a look instead: the tool `edit_place_on` |
| `light(id, kind=, **fields)` | `rect disk strip sphere spot distant dome` |
| `camera(id, **fields)` | a camera (looks along its −Z, Y up) |
| `rig(id, rig=, **fields)` | a camera rig: `orbit crane dolly` (a holder: `with rig(...):`) |
| `import_usd(id, file=, parts=[…], **fields)` | a 3D file by reference: USD, glTF / GLB, OBJ, FBX or Alembic (also a holder) |
| `combine(id, op=, **fields)` | a live boolean: `union subtract intersect` of the meshes made inside `with combine(...):`, the first the base (guide `modelling`) |
| `copies(id, source, layout=, count=, **fields)` | one thing many times: `source` (an item or list made earlier in the same list) goes inside; or `with copies(...):` and make it inside (guide `copies`) |
| `garment(id, pieces=[…], seams=[…], sewTime=, **fields)` | a garment from flat sewing-pattern pieces sewn at their edges; it is cloth, and its pieces' `at` are heights in the scene (it is not set on the ground) (guide `simulate` › Garments from patterns) |
| `copies.effector(kind=, near=, radius=, amount=)` | change the copies near an item: `scale turn push colour` |
| `clay(id, radius=, at=, to=, **fields)` | a clay starting as a ball of `radius` (a capsule from `at` to `to`); with neither, empty for `.lump` / `.draw`. No `at` / `y`: the ball stands on the ground, the clay's origin on the ground under it, so piece positions are heights above the ground; a piece below the ground lifts the figure (and what is attached) onto it (guide `sculpting`) |
| `clay(id, draw=[(x, y, z) …], facing=, puff=)` / `clay(id, spin=[…], axis=)` | a clay made from a drawn outline or a spun profile, in the scene: it stands at the drawing's middle, its X along it |
| `clay.draw(outline, facing=, puff=, mode=, blend=, symmetry=, name=)` | a drawn shape joined on (the clay's own space); a tiny one is a lump |
| `clay.spin(profile, axis=, mode=, blend=, symmetry=, name=)` | a spun shape joined on (the clay's own space) |
| `clay.lump(at, radius, to=, mode=, blend=, symmetry=, name=)` | a piece: a sphere at `at`, a capsule to `to`; `mode="carve"` cuts it out (the clay's own space) |
| `clay.shape(shape, at, radius, to=, mode=, …)` | the same piece with its shape named, as the `clay.shape` operation: `"sphere"` or `"capsule"` (needs `to`) |
| `clay.stroke(path=, dir=, brush=, size=, strength=, symmetry=, accumulate=, name=)` | a brush stroke: each dab where a ray from a `path` point along `dir` meets the clay |
| `clay.layer(name, amount=1.0, on=True, keys=None)` | a sculpt layer: the lumps and strokes after it go on it, applied after the Base at its Amount; `keys={seconds: amount}` makes it a face shape; `clay.layer(None)` goes back to the Base (guide `sculpting`, Sculpt layers) |
| `clay.bend(joint, {seconds: (x, y, z)}, ease=)` | turn a clay's joint by those degrees about the clay's own X, Y, Z (from rest) at each time; finds its joints the first time |
| `clay.pose(seconds, **{part: target, …}, holds=[…], ease=)` | one pose at that time (chain calls for motion): each part's end goes to its target, a world point `(x, y, z)` or `{"up": m, "out": m, "forward": m}` from where it is at rest (the figure's own directions); parts `"hand.R"`, `"right hand"`, `"picture-left hand"` (as the shot's camera sees it); out of reach / far side of the body: a note in the reply. The older `clay.pose(part, {seconds: target})` still works |
| any item: `attach_to=<item>` | it moves and turns with that item (`follow`); on a clay it bends with the bone nearest it (`followPose`) |
| `material(id, **fields)` | a material (lists at the top level, not in a group) |
| `shot(id, camera=, fps=, start=, end=, width=, height=, background=)` | a shot |

Every argument besides `id` is a field. The field names, ranges and defaults are the ones `inspect_operations` (the `<type>.add` / `<type>.set` entries) and `inspect_item` show; an unknown field, a wrong type or an out-of-range number fails (see Errors). Units: metres, degrees, seconds;
colours `"#rrggbb"`.

A field that doesn't apply as the item is made is not used, never stored: `width` on a sphere, `fStop` without `dof=True`, a
`strip`'s `length` on a `rect`, `seenByCamera` on anything but a dome. The script still runs, everything else in it is applied,
and the reply names each one (`strip.seenByCamera: not used on a strip light (it only applies when Kind is 'dome')`). Set what it
depends on in the same call (`shape=`, `kind=`, `dof=True`, `rig=`) to use it.

The fields, by item (all items also take `x y z rx ry rz sx sy sz px py pz visible`; a rig takes only `x y z rx ry rz visible`). `px py pz` is the pivot, in the item's own space: the point it turns and scales around; with a pivot, `x y z` is where the pivot stands. Items also take `follow` (an item to ride on, `followAmount` 0..1 keyed to pick up and let go; `followPose=True`: ride the bone of a posed clay nearest it) and `stick` (a mesh to stand on; `y` is then the height above it):

- **mesh** `shape width height depth radius tube bevel segments smooth material`; text: `text font size weight tracking lineHeight align`;
  svg: `svgFile` or `pathData`, `svgWidth`; path2d: `doc2d layer svgWidth`; outline faces: `frontMaterial bevelMaterial sideMaterial backMaterial`
  (`depth` is how far an outline is pushed out).
- **light** `kind length width height radius angle texture turn seenByCamera color intensity exposure temperature spread card lightsOnly normalize shadows`
  (`lightsOnly` is ids separated by spaces; `turn`, `texture` and `seenByCamera` are for a dome only; `length` for a strip).
- **camera** `focalLength sensorWidth dof fStop focusDistance focusItem near far` (`focusItem`: an item id kept sharp as it moves; `sensorWidth` spans the picture's width in every renderer and picture shape, the height follows the shape).
- **rig** `rig radius height angle armLength lift swing travel pan tilt handheld shake shakeFrequency shakeMove seed`.
- **material** `baseColor baseColorTexture metallic roughness roughnessTexture transmission ior coat coatRoughness anisotropy anisotropyRotation subsurface subsurfaceColor subsurfaceRadius bumpTexture bumpStrength emissionColor emissionStrength thinFilm sheen sheenRoughness sheenTint coatTint coatIor brushDirection`; `material(id, start="fabric", baseColor=…)` begins from a starting point (guide `materials`). A pattern (checks, stripes, weave) goes on as a block: `graph.add` + `graph.connect` (guide `materials`).
- **clay** `brush brushSize brushStrength symmetry accumulate detail material` (the brush settings are the next stroke's; `detail` is the smallest grain, metres).
- **copies** `layout count columns spacingX spacingY spacingZ radius faceOut surface amountBy density minSpacing alongSurface onlySeen seed varyMove varyTurn varyScale varyStart` (guide `copies`); **effector** `kind near radius falloff amount axis colour`.
- **import** `file prim material`; **part** `path material visible`.
- **Simulation** (mesh, combine, import, group, clay, copies, directly in the scene only) `simulate` (`off falls still`) `massFromSize mass bounce friction starts simShape`,
  or `item.simulate("falls", bounce=0.4)`; on a shot `simGround simTiming simSimplify`. A script never computes it: the `run_simulation` tool does (guide `simulate`).
- **shot** `camera fps start end width height background`; its render settings `renderQuality renderSamples renderDenoise renderSize renderRange renderStart renderEnd motionBlur shutter` (motion blur: camera-rigs.md)
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
- Items and keys the script no longer makes are removed (listed in the reply); things a person added themselves are left alone.
  Leaving out most of what it made runs, with a warning naming them (see "The way to work").
- Give a script a stable `name` (`run_script`'s `name`, default `agent_script.py`) and re-run under it to merge. A different name is a
  different script: its own new things go beside the first script's; what it makes under an id already in the scene, it takes over.
  A counted id (`mesh_1`) skips ids already in the scene.
- Don't change an id's kind between runs (`mesh("a")` then `light("a")`): use a new id. If a person had edited the old item, the run is
  refused, naming the fields the new kind doesn't have; if nobody had, the item is rewritten in place as the new kind.

## Recipes: settings a person can change

A **setting** is a value at the top of a script that a person may want to change without reading the script: how many
copies, a colour, a style. Declare it with `setting(...)`; the call gives the value to use:

```python
n = setting("count", 12, min=1, max=200, label="Copies")       # a number (a whole number when the default is one)
tint = setting("tint", "#c33a2a", label="Colour")               # a colour "#rrggbb"
style = setting("style", "round", choices=["round", "square"])  # a choice
lid = setting("lid", True, label="Lid")                         # on / off
title = setting("title", "Hello")                               # text
for i in range(n):
    mesh(f"post_{i}", shape="sphere" if style == "round" else "box", x=i * 0.3, material=material("paint", baseColor=tint))
```

A script with settings becomes a **recipe** in the scene, `recipe_<script name>` (`fence.py` gives `recipe_fence`): it keeps
the script, its settings and their values. Change a setting and the script runs again with the new value, under its own
name, through the same safe re-run as `run_script`:

- **An agent**: `edit_recipe {"recipe": "recipe_fence", "set": {"count": 30}}`; `edit_recipe {}` lists the scene's recipes,
  their settings, what each takes and what each made. Leaving out `set` runs the recipe again as it is.
- **What it made is replaced, never doubled**: 12 copies set to 30 gives 30 copies, set back to 5 leaves 5. A post a person
  moved by hand stays where they put it through every change.
- **One undo step**: `edit_undo` brings the old value back with the old copies.
- **A bad value is refused and changes nothing**, naming the setting and what it takes: `setting "count" is 500, out of range.
  Accepted: a whole number from 1 to 200`.
- **Re-running the script yourself** (`run_script`, same name): a setting keeps the value set in the recipe; the script's
  default is used only when the setting is new or you changed its default in the script (changing the default is how a
  script says "use this now"). Removing every `setting(...)` call removes the recipe; the things stay the script's.

A setting's name is a short word (letters, digits, `_`, spaces), declared once; its kind comes from its default.

## Changing the new scene's own things (shot_1, ground, sky)

A new document already holds `shot_1` (with `shot_1_camera`), `ground` (with `ground_material`) and `sky`. A script changes
them like its own, in the same run (one undo step):

- **Make it again under the same id** to replace it: `shot("shot_1", camera=cam, end=6, width=1280, height=720)`,
  `mesh("ground", shape="plane", width=60, depth=60, material=floor, backdrop=True)` (a new floor: the ground you made takes the old one's place;
  `backdrop=True` keeps it a floor a click goes through; a wall is just another mesh, there is none by default). Fields you leave out go
  back to their defaults: `light("sky", kind="dome", intensity=0.4)` is a plain white dome, the sky picture is gone (the camera sees a
  flat grey). To change only the brightness, `edit("sky", intensity=0.4)` instead.
- **`edit(id, **fields)`** (or `item(id)`) is a handle on a thing by its id, changing only the fields given:
  `edit("ground_material", baseColor="#2b2f36")`, `edit("ground").set(width=40)`, `item("cam").key("x", {0: -1, 3: 1})`. It works
  on anything directly in the scene (an item, material or shot), whoever made it, and on anything made earlier in the same
  script; asked twice, it is the same handle. Not yet on a thing inside another script's group: `edit_document` reaches that.
- **`remove(id, …)`** takes things out: `remove("shot_1_camera")` after `shot("shot_1", camera=cam)`; `remove("ground", "ground_material")`.

- **Your own lights add to the start lights.** The new scene's lights are `sky` (a dome), `key_light` and `rim_light` (panels).
  A light of your own keeps them; `light(..., replace_start_lights=True)` takes `key_light` and `rim_light` out (the reply
  names what it removed). A **dome** of your own always takes `sky` out (one sky). **Changed:** before, any light of your own
  took the key and rim out silently.
- **Brightness in stops:** `light("key", kind="rect", …, brightness=0).aim(subject)`: 0 lights the subject as the start key
  lights its own, +1 twice that, −1 half; it sets `intensity` (Same brightness at any size, scaled by the distance squared)
  and `exposure` (= the stops). The distance is to what it aims at, or `at_distance=` metres. A dome: exposure −1 + stops.
- **Made again, a thing keeps what you didn't say:** `shot("shot_1", end=3)` keeps its camera; `light("key_light",
  intensity=8)` keeps its place and aim. A shot with no camera is seen through the default view, and the reply says so.

The same goes for anything another script or a person made: **made again under its id**, this script replaces it (never a
second copy). From then on the script owns them: a re-run under its name changes them again, and what the new scene or the other
script had set is never held back. A field a person changed by hand is held back as usual (`force` lets the script win).

## Nesting

```python
with group("device", ry=-12) as device:
    mesh("body", shape="box", width=0.07, height=0.02, depth=0.1)
    with rig("spin", rig="orbit", radius=0.5):
        camera("cam")
with import_usd("phone", file=r"C:/assets/phone.usdc", parts=["Body/Screen"]) as phone:
    phone.part("Body/Frame", material=steel)       # material= and visible= on a prim inside the file
```

Only a group, a rig, an import, a combine or a copies holds items (a combine: meshes and combines only; a copies: what it repeats, then effectors). `with` on anything else is an error. An item's transform is relative to its holder.
Materials and shots always go to the top level, even when made inside a `with`.

## Handle methods

- `item.set(**fields)` changes fields after the item was made. Returns the handle.
- `item.key(field, {seconds: value}, ease="smooth")` animates a number or colour field (or `key.add`'s shape: a list of
  `{"t": seconds, "v": value, "ease": …}`). The first `key()` of a field in a run replaces that field's keys, so keying a thing taken
  with `edit()` never doubles its keys. A value can be `(value, "ease")` to
  give that one stretch its own ease. Colour fields take `"#rrggbb"` values. Call it again with another field to key more.
  Returns the handle, so `.key(...).key(...)` chains.
  Animatable: every number or colour field except a mesh's shape fields, a light's `spread`, and `aim`. A key's ease shapes the stretch
  that starts at it. Eases: `linear hold smooth snappy natural heavy easeIn easeOut easeInOut spring bounce custom`.
  Key ids come from the item, field and time (`cube.ry.k2000`), so the same script gives the same keys every run.
  Springs and curves: `item.key("y", {0: 0.1, 1: 0}, ease="spring", stiffness=240, damping=14)` (settings on every key), or per key
  `{0: {"v": 0, "ease": "custom", "x1": 0.2, "y1": 0, "x2": 0.1, "y2": 1.1}, 1: 30}`. A setting that doesn't fit the key's ease is not used, and the reply says so.
  `item.key("visible", {0: False, 1.2: True})` shows and hides: on or off from each key to the next, never in between.
- `item.aim(item_or_id)` or `item.aim((x, y, z))` points the item's −Z at an item's origin or a point, every frame (turns `rx ry rz` off while it aims).
  `item.aim(target, roll=90)` then turns it around the way it points: a strip light stands on end, a camera's horizon tilts. `roll` can be keyed.
- `import.part(path, **fields)` an override on a prim inside an import's file (paths from `inspect_model_file`).

## Inside the script

Python as usual (loops, functions, f-strings, `math`). Available: `range len min max abs round enumerate zip list dict tuple float int str sorted reversed sum isinstance`
and `import math`. Nothing else: no files, no other imports, no `print`. A script can't read the document, so it can't base a value on what a person did.

## Errors

A script that fails changes nothing. (A field that doesn't apply is not a failure: the script runs and the reply's warnings name
it, "a.width: not used on a sphere mesh … everything else was applied".) The error names the script and line, then what was wrong and what is accepted:

- `script "p.py" failed (line 4): … "wd" is not a field of a mesh. Accepted: shape, width, …` (a near miss gets a suggestion)
- `… a.ry at 1 s: ease='bogus' is not one of the choices. Accepted: linear, hold, …`
- `… "width" can't be animated on a camera; animatable: focalLength, …`
- `… id "a" is used twice in the script (already mesh).` (making it twice; `edit("a")` again is fine)
- `script "s.py" would remove 6 of the 7 things its last run made (…)`: send the whole script, or `remove(…)` them on purpose.
- `… cube is a mesh; only a group or an import holds items.`
- After the script runs, the whole document is checked: `the merged document would break its check: s.camera: no camera "nope" (there are: …)`
  (a missing material, a shot camera that isn't a camera, a shot that ends before it starts, an aim at itself). Still nothing is merged.

In `edit_document`, a taken id is refused naming what holds it: `id "top" is already used by a mesh`.

## What a script can't do (use `edit_document`)

- Delete anything inside a group, or move anything by hand (`item.remove`, `item.arrange`; `remove(id)` takes out a thing directly in the scene), duplicate (`item.duplicate`), rename (`item.rename`), or stop an aim (`item.aim off`): a script only describes what should exist.
- Change a single key's time, value or ease without rewriting that field's keys (`key.set`, `key.remove`, `key.clear`, `value.set`).
- Shape a key's curve: `custom` ease points and `spring` stiffness / damping are key fields only `key.set` reaches (a script's `spring` / `custom` use the defaults).
- Add a part to an import it didn't make, or anything to the document's own settings.
- Change something for one shot only (`<type>.set_in_shot`, e.g. `light.set_in_shot` with `shot`) or make collections (`collection.add`): a re-run never touches either, so a person's per-shot changes stay.
- Use markers: shot and key times in a script are plain seconds.
- Look at anything. After each run use `look_frame`, `look_frame what "sheet"` and `look_at`.
