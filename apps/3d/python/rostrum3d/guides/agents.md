# Building, looking and fixing a 3D shot

New here? `inspect_guide` `start-here` first (the loop and the core tools), then `getting-started` (a small clay character, step by step). This page is the depth behind them. Each tool's long description and every argument: `tool-details`.

**The way to work: write the whole scene as one Python script, look, edit the script, re-run it under the same name.** A re-run
replaces what the script made (values, keys, things you deleted from it) and keeps what a person changed by hand. Keep the
script in a .py file (`run_script` `path`) so each edit is the whole scene. `edit_document` is for one-off fixes a script can't
reach. Guide `script`: the API on one page.

**Look first, judge it yourself.** `look_frame` (the live preview: Storm, what the window shows, 960×540, under a second; the reply's last line says which quality) is the main check: write, look (or a sheet), change, then render. Nothing blocks you: a render always writes what you asked under the name you asked, and a shot with no camera is seen through the default view (the reply says so). If you want measurements, pass `notes: true` on `look_frame`, `look_motion`, `run_script` (with `look`), `render_still` or `render_video`: the reply then ends with `Notes (n): [id] what (when) | …`, things seen and measured, not orders. Off by default. What the notes can name: a frame too dark or blown out, a subject cut by the frame's edge, something floating above or sinking into the ground, a part come apart from its figure (`separated:arm`: shapes joined or grouped and touching at the start, apart later), a moving subject leaving the picture (`leaves_frame:cube`), no floor anywhere in the picture (`no_floor:<shot>`), a photographed sky seen past the floor (`backdrop_edge:<dome>`), a posed figure's part passing into another (`through_body:buddy.forearm.R`: the joint and how deep, when) or coming up against it so the two read as one lump on the picture (`touches_body:buddy.arm.R`), a mirrored pair of features that differ (`face_unmatched:eye_l~eye_r`: size or height at rest, or one showing much smaller on the picture), a small thing on a figure sliding off the part it sits on (`off_body:eye_l`: attach it with `attach_to=`), such a feature seen on the outline of a turned part so it reads as beside it (`on_rim:eye_l`: turn the part less at that time, move the feature round toward the camera, or turn the camera), a keyed back-and-forth swing too small to see on screen (`reads_still:buddy.forearm.R`: how far it moves; `wave_small:buddy.forearm.R`: each swing's share of the picture's height), a swing that repeats on the whole or half second so stills one second apart show the same pose (`wave_in_step:buddy.forearm.R`), two things not built as one passing into each other by their real forms, deeper than 1 cm (`passes_through:ball~cone`: which to move, how far, which way and at which key (a thing wholly inside a see-through one, liquid in a glass bottle, is not one); touching is fine), the shot's last 2 s or more with nothing moving at all (`frozen_end:<shot>`, on whole-shot checks, not a one-frame look or a still: carry a settle or idle to the end, or end the shot sooner), and a cloth or falling copies on the frame's edge where the stored simulation has them. `look_motion` notes the same from the document alone.

You work on a document, never on the USD file: every change is an operation (`run_script`, `edit_document`), and the engine builds the
scene from the document each time you look. One `edit_document` call is one undo step, its operations in `ops`:
`{"ops": [{"op": "mesh.add", "args": {"id": "ball", "shape": "sphere", "radius": 0.1}},
{"op": "mesh.set", "target": ["ball"], "args": {"y": 0.1}}]}` (`op`, then `target` (ids) and `args` (the fields)). Imported files (USD, glTF, OBJ, FBX, Alembic) stay untouched; your changes to them are overrides.

A new scene is not empty: it holds a wide neutral `ground` (a plane, material `ground_material`, `backdrop=True`: a
right-click on it in the window is a right-click on empty space), the sky `sky` (a dome light
showing the photographed Studio sky, `texture="sky:studio"`), two lights aimed at the middle (`key_light`: a 0.3 m `rect`,
`normalize` on, intensity 16, on the camera's left 1.6 m up, casting a contact shadow close under what stands there; `rim_light`: a 1 m `strip` on end behind on
the right, no shadows, for an edge; the sky at `exposure` −1.5 is the fill) and the shot `shot_1` ("Shot 1") through the camera
`shot_1_camera`, 55 cm up and 1.6 m back looking 15° down at the middle of the ground (no horizon in the picture; the Studio sky lights and reflects but the camera never sees it: past the ground a low camera sees the shot's plain `background`, the far floor's tone),
framed for things a hand to an arm tall. So the first look is lit
and framed before you add anything. A script keeps all of it unless it replaces it: `edit("sky", intensity=0.4)` / `edit("ground_material", baseColor=…)` change one field; a dome of your own (any id) replaces the sky; a light of your own ADDS to `key_light` and `rim_light` (`replace_start_lights=True` takes them out, and the reply names them); made again, a thing keeps the fields you did not give (`shot("shot_1", end=3)` keeps its camera); `remove("ground")` + `remove("ground_material")` or a mesh made again as `ground` replaces the floor (guide `script`, "Changing the new scene's own things").

## The loop

1. **Know the shot.** `inspect_shot` gives the frame rate, the frame range, the picture size, the shot camera and every light.
   `inspect_model_file` shows what a file you want to import holds before you import it: USD, glTF / GLB, OBJ, FBX or Alembic; its
   unit, up axis, animation (frames, fps) and parts (their materials and sizes).
2. **Build with one script** (`inspect_guide` `script`), grown in small steps: the room and the subject first, then the camera,
   then light, then materials, then motion. Each step is an edit to the same script, re-run under its name, then a look.
3. **Look through the shot's camera, not around the scene.** Everything you see is what the final picture will hold.
   Every look picture is saved in the project's `looks` folder (the reply gives its full path); it stays after the session.
   A look that takes longer than a moment (a `final` one, a busy machine) answers "Job … is running" with a `job_id`:
   ask `inspect_job` with it (and `wait_s`) for the picture. Read the picture only from the finished reply.
   - `look_frame` — one frame. Quality `fast` (Storm) tells you composition, scale, framing and motion in under a second;
     `final` (Cycles) tells you light, glass, shadows, reflections. `renderer: "stylized"` draws the stylized look: a
     material's Lines and Halftone show only there, its Light to colour there and in `final` (guide `materials`, "Stylized
     blocks"); with no `renderer` or `quality`, a shot whose Quality is Stylized is drawn stylized (`look_frame what "sheet"` and
     `look_frame what "shots"` too). It fails, naming what to build, when the stylized renderer isn't built. `onion` adds the person's onion-skin ghosts of one item (quick looks only).
     `view` looks from anywhere without moving the shot camera: `{"around": "buddy.head", "turn_deg": 90}` (the side) or `{"from": [x, y, z], "to": "ball"}`.
     Its reply says how much of the picture is clipped (blown to white) and, for a quick look, which lighting settings only
     Final applies ("Applied in Final: spread on rim, linking on rim"). For every text in the picture it also says which way
     it reads from this camera: left to right, mirrored (seen from behind), upside down, tilted (its angle to the horizontal)
     or edge-on; a text behind the camera or outside the picture is not listed. Fix a text that reads wrong by turning it
     (`ry` 180 turns its back to the camera) or moving the camera, then look again.
   - `look_frame what "sheet"` — the whole shot in six frames. Ask for it after every change to motion: does the thing arrive, hold, leave?
   - `look_motion` — the motion in numbers, every frame, read from the document (no picture, no renderer): per moving item
     its path (world metres and px on the picture), peak speed and stops; then what it saw: two shapes passing through each
     other (both named, the frames, how deep), sudden jumps (a snap or teleport between two frames), an item partly or
     wholly out of the picture. Overlap is judged by each shape's own box, so a hollow case counts as full: check a
     "passes through" with `look_frame` at those frames. `items` for a few, `frames` [first, last] for part of the shot,
     `full` for the speed on every frame. `path: "buddy.hand.L"` (or an item) instead measures that part on the picture:
     place per sample (0–1), speed, travel as a share of the picture's height, and a frame with its trail drawn on it. A thing set to Falls is measured where the stored simulation has it; when the
     simulation is out of date or not computed the reply says so first and is no all-clear (`run_simulation`, wait with
     `inspect_job`, look again). A cloth's folds and each copy of a falling copies item are listed as not measured. An **On screen** line (also from `render_video`, `look_frame what "sheet"` with `notes: true` and `run_simulation`, for the frames they cover: a cut that opens mid-drop, a shot that opens mid-fall, a still last stretch) per falling
     thing and cloth says how many frames of its drop (until it first lands) the shot camera shows, and names a fall that happens above
     or outside the picture or starts already at rest, with the fix (`sim.start_in_view` / script `.start_in_view()`, and `fallStart`, which
     holds a falling thing or a cloth in the picture until that second; [Simulate](simulate.md)).
   - `look_frame what "shots"` — one sheet for several shots, a row per shot (`shots` by id or name, default all; `count` frames per row,
     each tile labelled with the shot's name, frame and time; `quality` / `renderer` as look_frame what "sheet"). Use it to compare the
     framing of a sequence or two ends of a cut; an unknown shot fails and lists the document's shots.
   - `look_frame what "material" material=<id or name>` — that material on a ball (`shape: "plane"` for a flat square) turned through 4–8
     angles in one strip, lit by the scene's own lights with everything else hidden. It picks Final (Cycles) by itself for
     glass, metal, clear coat and Final-only settings and the reply says which renderer drew it and why; `quality: "fast"`
     forces Storm. Judge a material's highlight and colour here before assigning it; an unknown material lists the known ones.
   - `edit_place_on what "highlight"` — put a light's highlight on what is at a pixel of that picture (`fresh=true` for a light just
     added: distance and a starting brightness too). The lighting guide explains it.
   - `look_at` — "what is at this pixel?" Give x, y of the picture you were just shown (same width). It answers with the item id,
     the part, its material, the point in the world and the distance. Use it to find the id behind something that looks wrong,
     and to check a thing is where you meant (several points at once with `points`). On a clay it also names the **step**
     that made the surface there (`step`: id, name and kind, "arm, drawn"; a mirrored step counts on both sides) and, once
     its joints are found, the nearest **joint** ("forearm.R", 3 cm off): talk about parts by those names.
   - `look_frame highlight="steps:arm"` (or `"steps:arm,foot"`, names or ids) outlines what those steps made on the
     picture, each in its own colour, posed as the clay stands; the reply gives each region's box in pixels and says if
     another item hides part of it. Use it before reshaping a step: is "arm" really the arm you see?
   - `look_frame what "shape" target=<clay or mesh>` — the form, not a lit picture: outlines from the front, the side and the top on one
     scale, with its measures in numbers (height, width, depth, the width at every tenth of its height, the widest, the
     left–right difference and, on a clay, thin spots). Check proportions and symmetry here after every few modelling
     steps: "51 cm tall … widest 75 cm at 59 % height … left and right differ by up to 3.6 cm at 70 % height".
   - Paint: `look_frame what "paint" target=<mesh or clay>` (the paint picture, a layer or a channel, zoom and grid in canvas px),
     `inspect_paint_strokes` (each stroke: where it landed, on which items, how many px off), `look_frame what "coverage"` (how much
     of each item the shot sees is painted, unpainted hatched orange) and `look_frame what "where"` (a canvas spot or uv → its pixel
     on the shot and its world point). `look_at` adds `normal`, `faceSet` and `painted` (the top paint layer there).
     Guide `painting`.
4. **Fix the cause, not the picture.** If a shadow is wrong, look at the light's position and size, not at the surface it falls on.
   If something is too small in frame, check the camera's focal length and the distance before scaling the object.
5. **Render last.** `render_still` (png for people, exr for the Editor, its `passes` as layers) and `render_video` are jobs: they return a job id at once;
   `inspect_job` with `wait_s` shows `frame n of m`. Draft a video with `quality: "fast"` first. `render_video` also makes a small
   `<name>-share.mp4` beside the mp4, and `output_folder` (+ `file_name`) copies both where a brief asks for them (checked before rendering).
   Before a long render, ask `render_estimate` (see "Render settings and the time estimate" below).
   Another job on the same graphics card can make every frame many times slower, and a probe taken then shows it.
   Jobs run one heavy job at a time, the rest waiting in order: `inspect_job` without `job_id` lists them (running, waiting,
   ended); `run_stop job_id=…` cancels one, ending its own engine process; a cancelled `render_still` leaves nothing on disk. A stopped or failed shot render (`render_video`, the queue, the sheet)
   keeps the frames it finished in its `vNNN.partial`; the same call again, with nothing rendered changed, continues from them and
   its reply says "Continues from N finished frames".
   The person's Render page queue (render.queue.add / move / cancel) is the same kind of queue.

6. **Hand it on.** `render_send_shot shot=<id> scene=<2D item>/<scene id>` puts the shot into a 2D scene as a 3D render layer
   (2D's `render3d`, with `shot` set), one step in that 2D document's history. It uses the shot's newest render if its
   manifest's `scene_hash` matches the document now; else it renders first (`render_video` with EXR frames, the shot's
   own render settings) and is a job. Sending again updates the same layer. 2D says "out of date" when this document's
   content changes after the render (an identical script re-run is not a change). `target: "editor"` fails: the Editor
   isn't built yet.

## Asset library

Free CC0 models from Poly Haven and ambientCG. `edit_import_asset what "sources"` lists the sources and whether each is on;
`edit_import_asset what "search"` {source, query, page} searches an on source (40 a page: id, name, thumbnail address);
`edit_import_asset` {source, id, x, y, z} downloads the model into the project folder (`assets/<source>/<id>/`,
reused when already there) and imports it with `import.add`, its base at x y z, in one change. Every source is off
until the person switches it on in Import › Asset library; you can't switch one on, and the tools fail plainly while
it is off: tell the person instead. Then look at the model through the shot camera.

## Render settings and the time estimate

A shot carries its own render settings as fields, set like any other shot field in a script
(`shot("main", camera=cam, renderQuality="final", renderSize="half", renderRange="range", renderStart=1, renderEnd=3)`):

- `renderQuality` `draft` (32 samples), `good` (128, the default), `final` (512), or `custom`. Each preset includes noise clean-up.
- `renderSamples` and `renderDenoise` exist only with `custom`.
- `renderSize` `full`, `half` or `double` of the shot's `width` x `height`.
- `renderRange` `shot` (all of it) or `range`; then `renderStart` and `renderEnd` are seconds from the start of the shot,
  and the frame at `renderEnd` is the last one.
- `renderFormat` `png` (the default), `exr` or `both`: what the screen's render sheet saves.
- `renderOnly` a collection id (`""`, the default: everything): the shot renders that collection's items alone; lights,
  cameras and the groups holding members stay, everything else that draws is hidden in that shot (e.g. the characters
  on their own, then the set without them in a second shot, for the Editor). Exists once the scene has a collection.
- The passes an EXR carries, switches that exist only while `renderFormat` is `exr` or `both` and Quality is not Stylized:
  `passLight`, `passShadow`, `passReflections`, `passMasks` (on by default), `passDepth`, `passNormal`, `passLightGroups`,
  `passCryptomatte`, `passMotion`. A call's `passes` (`["light", "shadow", "reflections", "masks", "depth", "normal",
  "lightGroups", "cryptomatte", "motion"]`, `[]` = the picture alone) overrides them for that call; without it,
  `render_still` and `render_video` (with `exr`) use the shot's switches.

**Passes in the EXR** (Cycles only; the manifest's `exr` part lists every channel, its layer and which item each mask is):
`light.R/G/B` (matte surfaces' light), `reflections.R/G/B` (glossy), with either `rest.R/G/B` (glass, glow, sky, haze), so
`R G B = light + reflections + rest` before noise clean-up (exactly with `denoise: false`); `shadow.A` (0 lit .. 1 in full
shadow; it renders each frame twice, so it doubles the time, and the estimate counts it); `masks.<item id>` (hard-edged);
`depth.Z` (metres, 32-bit; 0 where nothing is); `normal.X/Y/Z` (world space, Y up);
`lightgroup_<light>.R/G/B` (one per light, named as the light's id, a dome too: that light's share of the picture; they add up to
`R G B` before noise clean-up, less surfaces that glow on their own; not cleaned of noise; the manifest's `light_groups` names
each); `CryptoObject00..02.R/G/B/A` (Cryptomatte masks per top-level item, soft-edged, with the names in the file's header, as
Nuke, Resolve and Natron read them); `motion.X/Y/Z/W` (motion vectors in pixels, x right, y up, Blender's Vector layout:
X Y = a frame before minus now, Z W = now minus a frame after; **with `motion` the picture renders sharp**, the shot's motion
blur is not used, so the Editor blurs from the vectors).

`render_still`, `render_video` and the Render button all read these same fields, so what you time is what is drawn.
Asking for something else in a call (`quality`, `width`) changes only that call, not the shot.

`render_estimate` says how long a render will take, measured on this machine, without rendering it. It is a job: ask with `inspect_job`.

- The first call for a scene draws the middle frame a few times and keeps the timing: two warm-up frames (not timed), at a
  quarter of the pixels with 8 samples and with the job's samples (that one is the probe picture), and once at the real size
  with the job's samples, because a full-size frame does not cost exactly four quarter-size ones. A very heavy job (that frame
  expected over 9 s) draws the real size with 8 samples instead and adds the quarter's extra time for the samples.
  About 12 s at full HD, Good; on a free card within about a quarter of the real render (tests: 0.75-1.15x the real
  time at 8-512 samples, for stills and 24-frame videos). Past a minute and a half it
  stops (its engine ended), the job fails and says the job is at least that slow or the engine stopped answering.
- Asking again answers at once. Changing only samples, size or the frame range answers at once too: the kept timing is re-scaled.
  Changing the scene (anything you see) measures again.
- `quality`, `samples`, `size`, `start` / `end` try other settings without touching the shot. `frame` estimates a still.
  `all_shots: true` gives each shot with its own settings, and a total.
- `budget_min` is the minutes you can spend. Over it, the reply names one-setting changes that should fit (fewer samples, a smaller size),
  each with its time, worked out from the measurement: halving the samples does not halve the time, so it may name far fewer.
- `render_video` with `budget_min` or `estimate_only` uses this same measurement (kept for the scene), so it agrees with
  `render_estimate`, and fewer samples never estimate longer.
  The reply waits (up to 25 s) for that measurement and answers at once: `estimate_only` returns the figures (frames, seconds, seconds a
  frame), also when they are over `budget_min` (then with the settings that fit); `budget_min` alone renders either way, and when over,
  the reply says so at once ("Rendering anyway: … over the 9.0 min budget") with the settings that fit, for next time.
- Look at the probe picture it returns: it is what is about to be drawn.
- It is a close guide, not a promise: start-up and encoding do not shrink with the settings, and time grows with samples much
  less than in step (a straight line in the log of the samples, as measured).
- When another job is using the graphics card, the reply says so (`gpu_busy`, also in the text): renders are slower while it runs,
  about twice. A probe taken then is not kept; ask again once the card is free for a clean figure.

## Your time

Every reply of this server ends with a line: the time since your first call (real time, your thinking included), the number of calls,
whether the picture was looked at since your last edit, and, when the session has a limit (`ROSTRUM_SESSION_BUDGET_MIN`), the minutes left.
After a finished video it also says how many more passes of look, fix and export the time left allows (each is the video's measured
time plus about 2½ minutes of looking and fixing). A first video is rarely the last: the reply of `render_video` names the next pass, and
the line tells you whether there is time for it. Look at the video's frames (`look_frame what "sheet"` for the whole move, `look_frame` at the weakest
times, `look_motion` for what moves), name the three weakest moments, fix them with `run_script`, and render again to the same name.
The time left is a number to use, not a reason to stop early.

## Techniques

- **Frame first, light second, detail third.** A box-and-sphere blockout with the right camera and light already shows if the shot
  works. Add detail only where the camera sees it (a part that never reaches the frame costs render time and gives nothing).
- **A look at fast quality is not a look at final.** Storm has no true glass, soft shadows or global light. Judge shape and timing in
  Storm, then confirm light and materials with one `final` look at the frame that matters most. (A person on the screen gets the
  same with Shift+F, Look: Final: the viewport itself runs Cycles with the Render button's settings and cleans up sample by sample.)
- **A stylized material is judged in the stylized look.** After `material.set` with `lines`, `lightToColor` or `halftone`,
  look with `renderer: "stylized"` (Lines and Halftone are invisible in `fast` and `final`). Its bands follow the real lights:
  move or brighten a light to move the lit / shadow edges, or change `shadowBelow` / `litFrom`. For the finished pictures,
  set the shot's `renderQuality` to `stylized`: `render_still` / `render_video` without `renderer` or `quality` then render
  Stylized (drawn at twice the size and smoothed down), and so do the person's Render button and render sheet. Or pass
  `renderer: "stylized"` for one render of any shot.
- **Patterns and variation come from blocks.** A material's Blocks view is open to you as operations: `graph.add`
  (a Noise, Image, Ramp, Mix …), `graph.connect` (`from: "noise_1.value", to: "surface.roughness"`), `graph.set`,
  `graph.remove` (materials.md › For agents). A worn metal: Noise into a Ramp into Roughness; a printed label: an Image
  into Base colour. Check with `look_frame what "material"`: it draws the blocks and lists them and their wires in the reply.
- **Depth of field is a choice of three numbers.** The focus distance is the distance from the camera to what must be sharp. Get
  it from `look_at` (its `distance`) instead of measuring by eye. Or name what must stay sharp: `camera.set focusItem=<item id>`
  (with `dof` on); the distance then follows that item's origin every frame, along the way the camera looks. `focusItem=""`
  goes back to `focusDistance`. Real lenses: 24, 35, 50, 85, 105, 135 mm (`focalLength`; any value works).
- **Another angle is another shot.** `shot.from_view` with `position` [x, y, z], `turn` [rx, ry, rz] (degrees, it looks along
  its −Z) and `focalLength` makes a camera and a shot through it in one step ("Shot N", the first shot's size, frame rate, time
  and render settings; `id`, `name`, `cameraId` optional). A camera may serve several shots; each shot is its own window of time.
- **Only in this shot.** One scene, several shots, and a shot needs its own tweak (the key light nearer and brighter for
  the close-up, a prop out of frame hidden): `light.set_in_shot` with `shot: "close_02"` and the settings, the same ones
  `light.set` takes (`mesh.set_in_shot`, `camera.set_in_shot`, `material.set_in_shot`, one per type). That shot alone
  shows it; the others keep the scene's value. A keyed setting holds that one value through that shot (its keys still
  play in the other shots). What kind of thing it is (a light's `kind`, a mesh's `shape`) is the same in every shot.
  `shot.clear_override` (target: the shot; `item`; `fields`, all when left out) puts it back. `inspect_item` on the shot
  shows its `overrides`. Your script re-run never wipes them, a person's or yours.
- **Collections.** `collection.add` (`name`, `items`: ids, and / or `material`: every item using that material, now and
  later) makes a named set. A light's `lightsOnly` may name it (it lights every member); `collection.material` gives
  every member a material, `collection.show` (`visible`, and `shot` for one shot only) hides or shows them all;
  `collection.set` (`items`, `include`, `exclude`, `name`, `material`) changes it, `collection.remove` deletes it (the
  items stay). Each call is one undo step.
- **Move a shot's own camera.** `shot.take_view` (target the shot) puts its camera at `position`, looking at `lookAt` (both
  world), with `focalLength`: one step, inside a group or on a rig it stays there, an aimed camera aims at `lookAt`, a camera
  with keys gets a key at `at` (seconds). `shot.frame` with `items` [ids] (shapes, clay, groups, copies, lights …) frames them: the camera keeps its direction and lens
  and moves so they sit in the middle and fill the picture with a 10 % margin (aimed at an item, it only goes nearer or
  farther). Check the result with a look at the shot.
- **Time.** `at` is seconds from the start of the shot; `frame` is the shot's own frame number. Both are valid in every tool; the
  replies carry both `time` and `frame`.
- **Check the ends of a move.** First and last frame of a move, and the middle: `look_frame what "sheet"` with `start` / `end` zoomed to that range.
  `look_motion` after each change to keys: it names the frames where something passes through another thing, snaps or leaves the picture.
- **A word or a logo.** `mesh.add shape=text text="Rostrum" font=Inter size=0.2 depth=0.03 bevel=0.002` makes a word 0.2 m
  tall (the em), pushed out 0.03 m; it is centred on its origin, so spinning it turns it around its middle. `size`, `depth`
  and `bevel` are metres; try a depth of about a tenth of the size and a bevel a tenth of the depth. A bevel too big for
  the outline fails with "Accepted: at most … m for this outline": set `bevel` to that number (or less). New lines in `text`
  make lines (`lineHeight` × size apart); `weight` 100–900 on the shipped fonts; `tracking` is thousandths of an em.
  A logo: `shape=svg svgFile=<absolute .svg> svgWidth=0.4` (or `pathData="M0 0H10V10Z"` for a shape you write yourself;
  y points down as in SVG), or `shape=path2d doc2d=<2D item id> layer=<path layer id> svgWidth=0.4` to extrude a path drawn
  in Rostrum2D. Only filled shapes count, and a shape drawn on top of another is merged with it, so make holes with
  path data (opposite winding, or fill-rule evenodd) rather than a white shape. Give the faces different materials with
  `frontMaterial`, `bevelMaterial`, `sideMaterial`, `backMaterial`. Check it with `look_frame` from the front and a turned view.
  Which way it faces: as made, a word reads from +Z (the default camera's side) with its letters' tops along +Y. Laid flat on a
  top face with `rx=-90`, it faces up and its tops point to −Z, so it reads from a camera on the +Z side looking down; `ry=180`
  then turns it to read from −Z. Upside down = turned 180° (fix with `ry` when it lies flat); mirrored = seen from behind (it is
  facing away: fix with `rx` / `ry` by 180°, never by a negative scale).
- **Cut, join, keep the overlap.** A port, a slot or a recess is a live boolean: `combine.make` on the base and the cutters
  (`op: subtract`), or `with combine("case", op="subtract"):` in a script. The cutters stay items; move one and look again.
- **Push and pull faces.** `mesh.edit` makes a shape or combine an editable mesh; then `faces.extrude`, `faces.inset`,
  `edges.bevel`, `edges.loopcut`, `mesh.knife`, `faces.material`, `edges.sharp` and `mesh.transform` with a selector
  (`"top"`, `"faces facing +y"`, `"faces 3"`) — never guessed numbers; `mesh.set subdivide=2` smooths it. Modelling
  guide, "Editable mesh".
  Guide `modelling` has the whole technique and its errors.
- **Many of one thing.** A row, grid or ring, a scatter over a surface (grass, pebbles, confetti), or a run along a word's or drawing's outlines (layout `path`): `copies.make` / `copies.scatter`
  (script: `copies(id, source, layout=, count=)`), 10,000 at most, drawn as instances; scattered copies the shot camera never sees are
  left out, and `look_frame` says how many it saw. `copies.hold` keeps one copy where you put it; `effector.add` makes the ones near an
  item bigger, turned, pushed, moved, hidden or tinted, in a sphere round it, behind a wall through it or in noise patches, following
  that item as it moves. Guide `copies`.
- **Things that fall and land.** `sim.body` kind `falls` on what drops (a copies item: every copy), `still` on what it lands on
  (the ground at height 0 is there by default), `sim.set` for mass, bounce, friction; then the `run_simulation` tool (a job). It is
  stored and only recomputed when something it depends on changes; renders compute it first when it is out of date, never
  render an old one. `run_simulation what "status"` says where it stands; `sim.to_keys` turns it into ordinary keys you can nudge. Guide `simulate`.
- **Clay.** For soft, organic forms (a head, a creature, a rock): `clay.add` makes a clay from a drawn outline
  (`draw`: scene points, `facing` the plane's normal towards the viewer, `puff` 1 = round), a spun profile (`spin`,
  `axis`) or a ball (`at`, `radius`); its shape is its list of steps, applied in order. `clay.draw` (`outline`) and
  `clay.spin` (`profile`) join more, in the clay's own space: start the outline on the surface where it should join.
  `clay.from_item` turns an exact part or import into clay (the original hidden). `clay.lump` joins a sphere (or a capsule, with `to`) or carves one out (`mode: "carve"`),
  `blend` = how softly it joins; `clay.shape` is the same with every setting spelled out. `clay.stroke` sculpts:
  `path` (points `[x, y, z]`) and `dir` (the way the rays point): each dab lands where a ray from a point along `dir` meets
  the clay, `brush` add, carve, smooth, pull, flatten, crease or mask (paints a mask that protects the clay from every
  other brush), `size` (radius, metres), `strength` 0..1, `falloff` (0 soft edge .. 1 hard), `spacing` (dab spacing, a
  share of the radius), `frontOnly` (never reach through to the far side), `invert: true` (flatten puffs out, crease
  pinches to a ridge, mask takes the mask away). Left out, they are the clay's brush settings (`clay.set brush brushSize
  brushStrength brushFalloff brushSpacing frontOnly symmetry accumulate`). Positions are in the clay's
  own space; `symmetry: "x"` (the default) mirrors across its X = 0. Each step is one undo step; `claystep.remove` takes
  one out, `claystep.set` renames it (`name`), hides it (`hidden`) or changes its numbers (`puff`, `blend`). **Sculpt layers**:
  `claylayer.add` (target the clay; `name`, `amount` 0..1) makes a group of strokes with an Amount and makes it the
  clay's `sculptLayer`, so the next `clay.stroke` / pieces go on it (a step's `layer`; `clay.stroke layer=` names one,
  `""` = the Base; `clay.set sculptLayer=""` goes back to the Base); `claylayer.set amount|on|name`;
  `claylayer.bake` (into the Base, as it shows now); `claylayer.remove` (with its strokes). The Base is made first,
  then each layer at its Amount; in a script `c.layer("smile", amount=0.5).stroke(…)`, `c.layer(None)` back to the Base. **Face shapes**: key a layer's
  `amount` (`key.add` on the layer's id, or `c.layer("smile", keys={0: 0, 1.5: 1})`): look_frame / look_motion and
  renders show each frame's shape (the clay is rebuilt per change of Amount, only the layer's strokes). Detail (the smallest grain) follows the shot cameras:
  about one grain per 1.5 pixels at the closest shot that sees the clay, so frame your shots and the clay is as fine as
  they need, never finer than the clay's size allows in memory (a 50 cm clay stops near 1.4 mm; `look_frame what "shape"`
  says "Detail held at …" when a close shot asks for more); `clay.set detailMode=fixed detail=0.001` fixes it (finer is
  slower and uses more memory). A person's strokes are recorded as dab files (`dabs: "clay/<hash>.dabs"`); a script re-run
  keeps them. Look with `look_frame` from two sides after each few steps, and `look_frame what "shape"` for the numbers: is it as
  tall as meant, are the arms the same length (a step with Mirror off, a one-sided stroke shows as a left–right
  difference at that height), is a neck or wrist thinner than a few grains (a thin spot: it may break up). `look_at`
  says which step made a spot, `look_frame highlight="steps:<name>"` shows all of it. The person's side: guide `sculpting`.
- **Paint on a model.** A mesh: `mesh.unfold` once, then `paint.add` (`channel`: colour, roughness, height (Relief),
  metal, glow) and `stroke.add` batches in the paint picture's pixels, through `edit_document`; `look_at` gives the
  `uv` under a pixel. A clay: no unfold; `stroke.add` with `anchors` (from `look_at`'s `local` and `localNormal`) and
  `reach` (metres), so the paint stays on its spots when the clay is reshaped. Fine detail on clay: a Relief layer;
  a whole picture as relief in one call: `paint.stamp` (guide `painting`). Wear and dust: a layer with `fill` +
  `fillColor` and `shapeMask` (`edges`, `cavities`, `up`, `thin`; `maskSpread`, `maskInvert`) via `paint.set`.
  From the shot instead: `stroke.add` with `viewPoints` in a `look_frame` picture's px plus the camera fields from
  `look_at`'s `view`, one per item the path crosses, in one call list. Check with `inspect_paint_strokes` and
  `look_frame what "coverage"`. Guide `painting`.
- **Timing a move.** Key with `item.key("rx", {0.8: 0, 1.6: -105})` in a script (or `key.add` with `t` seconds and `v`; the script's
  `key()` also takes that shape: `[{"t": 0.8, "v": 0}]`). `inspect_animations`
  lists an item's animations as the timeline shows them: Position (x, y, z) is one animation, a "Move"; Turn (rx, ry, rz)
  one "Turn"; Scale (sx, sy, sz) one "Scale"; any other field its own. Each has its stretches (the time between two
  neighbouring keys: `ids`, `start`, `length`, `ease`, `preset`, `from` / `to`). Ease a whole stretch with `anim.ease`
  (targets: the stretch's `ids`; `preset` linear, smooth, in, out, spring, bounce or hold, or a curve `x1 y1 x2 y2`);
  `key.scale` stretches or squeezes keys in time around a moment; `key.paste` copies keys onto the same fields of other
  items; `key.stagger` starts several items' keys one after another. Each is one change, one undo step, the same a
  person makes by clicking a stretch on the Animate page and picking "Out". Check the result with `look_frame what "sheet"`.
  **Show and hide** by keying `visible`: `key.add` with `v` 1 (shown) or 0 (hidden), or `item.key("visible", {0: False,
  1.2: True})` in a script. It switches at the key and stays until the next one, never part way, whatever the ease
  (an item hidden this way is gone from the picture, not shrunk; its Scale is left alone).
- **Stepped timing.** `timing` on an animated item or group: `smooth` (default), `on2`, `on3` (`mesh.set timing=on2`,
  or `mesh("bud", timing="on2")` in a script): every value then holds for 2 or 3 frames, counted from the shot's
  start, in the viewport and the render alike. A group's timing steps everything inside it; a child's own `on2` /
  `on3` wins. Leave the camera `smooth` and the character steps while the camera glides. The field only shows (and
  `<type>.set` only takes it) once the item or something inside it has keys.
- **Poses.** `pose.save` (targets: the items; `at` seconds; optional `name`, `id`) keeps their x y z, rx ry rz (not
  when aimed), sx sy sz as they are at `at`, in the document's `poses`. `pose.apply` (target: the pose; `at`) keys all
  of them at `at`; with `share` 0..1 it is a breakdown instead: each field keyed that share of the way from its key
  before `at` to its key after (fields without both are skipped and named in the reply, as are items no longer in
  the scene). `pose.rename`, `pose.remove`. Each is one undo step. Onion skin (the person's ghosts in the viewport):
  `look_frame` with `onion: {item, mode}` draws the same ghosts (mode `keys` = the item at its previous and next keys, `frames` =
  2 and 4 frames before and after; red before, green after). Quick looks only, not `final`. Use it to check an arc or spacing at
  one frame; `look_frame what "sheet"` shows the whole move.
- **Follow and stick.** `follow.add` (targets: the riders; `item`: what they ride on; optional `from`, `until` seconds)
  makes them move and turn with that item from where they stand, picked up at `from` and let go at `until`
  (`followAmount` keyed 1 and 0, held). Let go, they stay where they are then: no jump. `follow.release` (`at`) lets go
  later. Part-way amounts ride that share of each frame's move. `stick.add` (`item`: a plane, disc, box, sphere,
  cylinder, cone, capsule or editable mesh; optional `height`) stands them on its surface straight below; their `y` is
  then the height above it. Each is one undo step; the fields are `follow`, `followAmount`, `stick` (`<type>.set`).
  `follow.add` with `pose: true` on a posed clay (or a mesh with bones) rides the bone nearest each rider instead
  (`followPose`): an eye on a turning head. Parts placed on a clay get it already (`place_on`, `edit_place_on`).
  A hinge is a pivot: put `px py pz` on the lid's back edge (`x y z` is then where that edge stands) and key `rx`.
  `look_frame what "sheet"` shows whether the rider stays put after it is let go.
- **Posing a clay.** In the script: `buddy.pose(t, **{"picture-right hand": {"up": 0.22, "out": -0.15}})`, one pose
  per call, the joints found for you. A gesture reads on camera only when the part travels a good share of the
  figure's height, several times, to the shot's end (a wave: the hand over the head swinging about half the figure's
  height; guide `posing` › For agents has the example; a 2 cm move reads as still). As operations: `pose.find_joints` finds its joints from its
  shape (body, chest, arm.L, forearm.L, foot.R …), `pose.hold` keeps spots still, `pose.drag(part="hand.R", to=[x,
  y, z], at=t)` bends the chain back to the body and keys the Turn of every joint that moved, `pose.rest` takes the pose off, `pose.move_joint`
  places a joint by hand. Guide `posing` has the details (names, holds, keys, sculpting while posed).
- **Bones.** `bone.chain` (target: one mesh; `points`: two or more `[x, y, z]`, root first, world positions at time 0,
  or the mesh's own space with `space: "mesh"`) lays len(points) − 1 bones, each from one point to the next, nested
  (mesh › `<mesh>_bone1` › `_bone2` …), and binds the mesh (`skinned`), in one undo step; a chain the mesh had is
  replaced. A bone's own +Y runs along it from its head; its fields are `rx ry rz` (Turn, keyable) and `length`; its
  head `x y z` is data the chain wrote. Bend it by keying Turn: `key.add` (target the bone, `prop` rx / ry / rz, `v` =
  its rest turn plus the bend, in degrees; the window's bone rings write the same `key.add`); poses and `anim.ease` work on bones too. The core weights the mesh to the
  bones itself. `bone.bind` (`off: true`) stops the bending and keeps the bones; `mesh.set skinned` is the same. The mesh
  bends only where it has points along its length: the ready shapes have none along their straight part (`segments`
  go around), so use an editable mesh (`mesh.add shape="poly"` with your own `points` / `faceCounts` / `faceIndices`,
  or `mesh.edit` then `mesh.knife` across it). Check the bend with `look_frame what "sheet"`.
- **Lip sync.** A mouth is a group whose children are the mouth shapes: one mesh (or group) per shape of the nine
  (X rest, A closed M B P, B slightly open, C open, D wide open, E rounded, F puckered OO W, G teeth on lip F V, H tongue
  up L). Name the children so they say the shape (`mouth_rest`, `mouth_closed`, `mouth_wide`, `mouth_puckered` …; as
  in 2D a lone letter is the sound it makes, so "mouth A" is the wide AH), or give `shapeX` … `shapeH` yourself; any
  subset works, a missing shape shows the nearest one given. `inspect_voice_lines` lists the project's voice lines
  from RostrumSound (`<song>/<line id>`, the words, where each starts, whether its voice is made) and the mouths it
  finds in the scene. `lipsync.make` (target: the mouth group; `line`; or `file` + `text` + `at` for a WAV that is not
  a project line) hears the line once (the phone model; a few seconds to a minute, then cached), turns it into mouth
  shapes in time (the same timing as 2D) and keys every child's **Visible**: on while its shape shows, off while
  another does, so one shape shows at a time (its Scale is left alone). One undo step; the keys are ordinary keys,
  move or delete them on the timeline like any other. A second run adds keys only where there is none at that time.
  The person does
  the same: right-click the mouth group › **Lip sync…**, click a voice line, check the shape for each row, Apply.
  Check with `look_frame what "sheet"` over the line's seconds.
- **Memory.** `look_frame` replies carry the video memory the render used; a 4 GB card holds a modest scene at 1080p. If a
  render fails with a memory message, lower `width` or the number of lights before anything else.

## Errors

A failed look or render says what failed (the frame, the camera, the item) and, when the engine had stopped, that it was started
again. Read the line; it names what is accepted. A scene the engine refuses is refused whole, and the engine keeps the previous
scene, so a look after a refused change shows the last good state, not the new one.
A render with passes that "came out empty while its <layer> layer is not" wrote no file: the picture was lost on the way,
not the scene. Render again; if it repeats, report it with the engine log the message names.
