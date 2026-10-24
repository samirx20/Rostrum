# Building, looking and fixing a 3D shot

You work on a document, never on the USD file: every change is an operation (`run_script`, `edit_document`), and the engine builds the
scene from the document each time you look. Imported USD files stay untouched; your changes to them are overrides.

## The loop

1. **Know the shot.** `inspect_shot` gives the frame rate, the frame range, the picture size, the shot camera and every light.
   `inspect_usd_file` shows what a file you want to import holds (its parts, their materials and sizes) before you import it.
2. **Build with a script** (`inspect_guide` `script` is the whole script API on one page), small steps: the room and the subject first, then the camera, then light, then materials, then motion.
   Each step ends with a look.
3. **Look through the shot's camera, not around the scene.** Everything you see is what the final picture will hold.
   - `look_frame` — one frame. Quality `fast` (Storm) tells you composition, scale, framing and motion in about a second;
     `final` (Cycles) tells you light, glass, shadows, reflections. Use `renderer: "stylized"` to see the stylized look.
     Its reply says how much of the picture is clipped (blown to white) and, for a quick look, which lighting settings only
     Final applies ("Applied in Final: spread on rim, linking on rim").
   - `look_sheet` — the whole shot in six frames. Ask for it after every change to motion: does the thing arrive, hold, leave?
   - `edit_place_highlight` — put a light's highlight on what is at a pixel of that picture (`fresh=true` for a light just
     added: distance and a starting brightness too). The lighting guide explains it.
   - `look_at` — "what is at this pixel?" Give x, y of the picture you were just shown (same width). It answers with the item id,
     the part, its material, the point in the world and the distance. Use it to find the id behind something that looks wrong,
     and to check a thing is where you meant (several points at once with `points`).
4. **Fix the cause, not the picture.** If a shadow is wrong, look at the light's position and size, not at the surface it falls on.
   If something is too small in frame, check the camera's focal length and the distance before scaling the object.
5. **Render last.** `render_still` (png for people, exr for the Editor, its `passes` as layers) and `render_video` are jobs: they return a job id at once;
   `inspect_job` with `wait_s` shows `frames n of m`. Draft a video with `quality: "fast"` first.
   Before a long render, ask `render_estimate` (see "Render settings and the time estimate" below).
   Another job on the same graphics card can make every frame many times slower, and a probe taken then shows it.

## Render settings and the time estimate

A shot carries its own render settings as fields, set like any other shot field in a script
(`shot("main", camera=cam, renderQuality="final", renderSize="half", renderRange="range", renderStart=1, renderEnd=3)`):

- `renderQuality` `draft` (32 samples), `good` (128, the default), `final` (512), or `custom`. Each preset includes noise clean-up.
- `renderSamples` and `renderDenoise` exist only with `custom`.
- `renderSize` `full`, `half` or `double` of the shot's `width` x `height`.
- `renderRange` `shot` (all of it) or `range`; then `renderStart` and `renderEnd` are seconds from the start of the shot,
  and the frame at `renderEnd` is the last one.
- `renderFormat` `png` (the default), `exr` or `both`: what the screen's render sheet saves.
- The passes an EXR carries, switches that exist only while `renderFormat` is `exr` or `both`: `passLight`, `passShadow`,
  `passReflections`, `passMasks` (on by default), `passDepth`, `passNormal`. A call's `passes` (`["light", "shadow",
  "reflections", "masks", "depth", "normal"]`, `[]` = the picture alone) overrides them for that call; without it,
  `render_still` and `render_video` (with `exr`) use the shot's switches.

**Passes in the EXR** (Cycles only; the manifest's `exr` part lists every channel, its layer and which item each mask is):
`light.R/G/B` (matte surfaces' light), `reflections.R/G/B` (glossy), with either `rest.R/G/B` (glass, glow, sky, haze), so
`R G B = light + reflections + rest` before noise clean-up (exactly with `denoise: false`); `shadow.A` (0 lit .. 1 in full
shadow; it renders each frame twice, so it doubles the time, and the estimate counts it); `masks.<item id>` (hard-edged);
`depth.Z` (metres, 32-bit; 0 where nothing is); `normal.X/Y/Z` (world space, Y up).

`render_still`, `render_video` and the Render button all read these same fields, so what you time is what is drawn.
Asking for something else in a call (`quality`, `width`) changes only that call, not the shot.

`render_estimate` says how long a render will take, measured on this machine, without rendering it. It is a job: ask with `inspect_job`.

- The first call for a scene draws the middle frame a few times and keeps the timing: tiny (the warm-up), at a quarter of the
  pixels with 8 samples and with the job's samples (that one is the probe picture), and once at the real size with 8 samples,
  because a full-size frame costs far more than four quarter-size ones. About 10-15 s at full HD; past a minute and a half it
  stops (its engine ended), the job fails and says the job is at least that slow or the engine stopped answering.
- Asking again answers at once. Changing only samples, size or the frame range answers at once too: the kept timing is re-scaled.
  Changing the scene (anything you see) measures again.
- `quality`, `samples`, `size`, `start` / `end` try other settings without touching the shot. `frame` estimates a still.
  `all_shots: true` gives each shot with its own settings, and a total.
- `budget_min` is the minutes you can spend. Over it, the reply names one-setting changes that should fit (fewer samples, a smaller size).
- Look at the probe picture it returns: it is what is about to be drawn.
- It is a close guide, not a promise: start-up and encoding do not shrink with the settings, and time grows with samples much
  less than in step (a straight line in the log of the samples, as measured).
- When another job is using the graphics card, the reply says so (`gpu_busy`, also in the text): renders are slower while it runs,
  about twice. A probe taken then is not kept; ask again once the card is free for a clean figure.

## Techniques

- **Frame first, light second, detail third.** A box-and-sphere blockout with the right camera and light already shows if the shot
  works. Add detail only where the camera sees it (a part that never reaches the frame costs render time and gives nothing).
- **A look at fast quality is not a look at final.** Storm has no true glass, soft shadows or global light. Judge shape and timing in
  Storm, then confirm light and materials with one `final` look at the frame that matters most. (A person on the screen gets the
  same with Shift+F, Look: Final: the viewport itself runs Cycles with the Render button's settings and cleans up sample by sample.)
- **Depth of field is a choice of three numbers.** The focus distance is the distance from the camera to what must be sharp. Get
  it from `look_at` (its `distance`) instead of measuring by eye. Or name what must stay sharp: `camera.set focusItem=<item id>`
  (with `dof` on); the distance then follows that item's origin every frame, along the way the camera looks. `focusItem=""`
  goes back to `focusDistance`. Real lenses: 24, 35, 50, 85, 105, 135 mm (`focalLength`; any value works).
- **Another angle is another shot.** `shot.from_view` with `position` [x, y, z], `turn` [rx, ry, rz] (degrees, it looks along
  its −Z) and `focalLength` makes a camera and a shot through it in one step ("Shot N", the first shot's size, frame rate, time
  and render settings; `id`, `name`, `cameraId` optional). A camera may serve several shots; each shot is its own window of time.
- **Time.** `at` is seconds from the start of the shot; `frame` is the shot's own frame number. Both are valid in every tool; the
  replies carry both `time` and `frame`.
- **Check the ends of a move.** First and last frame of a move, and the middle: `look_sheet` with `start` / `end` zoomed to that range.
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
- **Paint on a model.** `mesh.unfold` once, then `paint.add` (`channel`: colour, roughness, height, metal, glow) and
  `stroke.add` batches in the paint picture's pixels, through `edit_document`; `look_at` gives the `uv` under a pixel.
  Guide `painting`.
- **Memory.** `look_frame` replies carry the video memory the render used; a 4 GB card holds a modest scene at 1080p. If a
  render fails with a memory message, lower `width` or the number of lights before anything else.

## Errors

A failed look or render says what failed (the frame, the camera, the item) and, when the engine had stopped, that it was started
again. Read the line; it names what is accepted. A scene the engine refuses is refused whole, and the engine keeps the previous
scene, so a look after a refused change shows the last good state, not the new one.
A render with passes that "came out empty while its <layer> layer is not" wrote no file: the picture was lost on the way,
not the scene. Render again; if it repeats, report it with the engine log the message names.
