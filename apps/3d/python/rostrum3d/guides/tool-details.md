# Every 3D tool in full

The long form of each Rostrum3D tool's description and arguments, moved here so the tool list stays short. Start with
`start-here`; read a tool's entry here when its short description leaves a question. The look family is one tool,
`look_frame`, and `what` picks the look ("frame", "sheet", "shots", "material", "shape", "paint", "coverage", "where",
"exposure"); `width` is always the picture's width in px (a sheet: each frame's; it was `tile_width` in "shots" and
"material" and `size` in "paint"). Placing a light's highlight is `edit_place_on` with `what: "highlight"`;
the asset library is `edit_import_asset` (`what` "import", "search", "sources"); a simulation's state is
`run_simulation` with `what: "status"`.

## look_frame

One rendered frame of a shot, seen through the SHOT's camera by the same render path as export: a PNG file and an image you can see. quality fast = Storm, final = Cycles (slower); renderer picks one by name (storm, cycles, stylized); neither on a shot whose Quality is Stylized = stylized. stylized = the stylized look: the only one that draws materials' Lines and Halftone (Light to colour shows in final too). through = a light's id: see from the light instead (what it shines on is the middle of the picture). The reply says how much of the picture is clipped (blown out; stylized: pure white, its picked colours are shown as they are), which lighting settings only Final applies (spread, light linking), so a quick look's missing effects are known, and for every text in the picture which way it reads from this camera (left to right, mirrored, upside down, seen from behind or edge-on, its angle to the horizontal; data `text`). onion = {item, mode keys|frames}: the item's onion-skin ghosts (red before, green after) as the viewport draws them, to check an arc or a spacing; a quick look only (not final), drawn by the live view, so no studio light or outline. highlight = "steps:arm" or "steps:arm,foot": outline (2 px, tinted, one colour each, labelled) what those clay steps made, by name or id (look_at's `step` names them); the reply gives each region's box in pixels and what hides part of it. A posed clay is outlined as posed. `notes: true` ends the reply with measured notes (e.g. too dark or blown out, a subject cut by the frame, something floating or sunk): `Notes (n): [id] what (when) | …`. Off by default; judge the picture yourself.

- `quality`: fast = Storm, the live preview (a few tenths of a second a frame), final = Cycles (path traced, what export gives). Not given on a shot whose Quality is Stylized: the stylized look.
- `renderer`: Overrides quality: storm, cycles or stylized (the stylized look: materials' Lines, Halftone and Light to colour, every other material plainly lit by the scene's real lights; guide materials).
- `width`: Picture width in px; the height follows the shot's shape.
- `through`: A light's id (rect, disk, strip, sphere, distant): look from where it stands along the way it shines (60° tall view, level) instead of through the shot camera, to aim it.
- `view`: Look from here instead, for this one frame; the shot camera and the document stay as they are. `{"from": [x, y, z], "to": [x, y, z] or a part}`, or `{"around": a part, "turn_deg": 90, "tilt_deg": 30, "distance": 2}` (from where the shot camera stands: turn walks round to its right, tilt looks from higher, distance default its own); `lens_mm` default the shot camera's. A part: an item id or a clay joint `"buddy.hand.L"`. Level, like an aimed camera; data `view` {eye, target, focal}. No text or notes (not the shot's picture).
- `onion`: Onion skin as in the viewport: the item's ghosts at other frames, red before, green after. Quick looks only (fast or stylized, not final); no ghosts are drawn when the item has no other keys or frames to show.
- `highlight`: Outline what clay steps made: "steps:arm" or "steps:arm,foot" (step names or ids, as look_at's `step` gives them). Each in its own colour, tinted, 2 px edge.

## look_frame what "sheet"

A contact sheet: `count` frames spread over the shot (or a range) in one image, each tile labelled with its frame and time. Drawn fast (Storm; stylized for a shot whose Quality is Stylized) unless you say otherwise. Use it to check a whole move at a glance; look_frame for detail. `notes: true` ends the reply with measured notes (e.g. too dark or blown out, a subject cut by the frame, something floating or sunk): `Notes (n): [id] what (when) | …`, and when the shot simulates a fall or cloth, an On screen line: the range opens mid-drop or after the landing, the last stretch doesn't move. Off by default; judge the picture yourself.

- `quality`: fast = Storm, the live preview (a few tenths of a second a frame), final = Cycles (path traced, what export gives). Not given on a shot whose Quality is Stylized: the stylized look.
- `renderer`: Overrides quality: storm, cycles or stylized (the stylized look: materials' Lines, Halftone and Light to colour, every other material plainly lit by the scene's real lights; guide materials).
- `width`: Width of each tile in px.
- `start`: Seconds from the start of the shot. Default 0.
- `end`: Seconds from the start of the shot. Default: the last frame.
- `count`: Frames in the sheet, evenly spaced.
- `cols`: Tiles per row. Default 3.

## look_at

What is at a pixel (x, y) of a picture from the shot camera at a frame: the item id, the part (prim), its material, the point in the world (metres), the distance from the camera and `normal`, the surface direction there (world, unit length: "facing [0, 1, 0]" is a top); on a mesh with face materials `faceSet`, that face's own material; on a mesh also `uv`, the spot on its unfolded surface (paint canvas pixel x = u × paintSize, y = (1 − v) × paintSize; guide `painting`; look_frame what "where" is the reverse) and, where it is painted, `painted` {layer, name, channel, colour, alpha}: the topmost shown paint layer with paint there; on a clay `local` and `localNormal`, the point and the surface's normal in the clay's own space (a clay paint stroke's `anchors`: [x, y, z, nx, ny, nz, pressure]; guide `painting`); on a posed clay also `rest`, the same spot on its rest shape: anchor paint there, as the screen does. On a clay also `step`, the step that made the surface there ({id, name, kind, label "arm, drawn"}; a mirrored step counts on both sides) and, once its joints are found, `joint` ({joint "elbow.R"-style name, distance in metres to that bone}): name parts by them in clay.step.set, look_frame highlight="steps:<name>" and pose.drag. Counted from the top-left of a width×height picture, the same whatever renderer drew it. `view` in the reply: this picture's camera as stroke.add's From the view fields (viewEye, viewTarget, viewFov, viewSize, viewFrame, viewShot): add `viewPoints` [[x, y, pressure], …] in this picture's px to paint from the view.

- `x`: Pixels from the left of the picture.
- `y`: Pixels from the top of the picture.
- `points`: Several points as [[x, y], …] (instead of x and y), up to 64 in one call.
- `width`: Width of the picture the pixels count in (the one look_frame gave). Default 960.
- `height`: Height of that picture. Default: follows the shot's shape.

## look_frame what "shots"

One contact sheet for several shots, ONE ROW PER SHOT: `count` frames spread over that shot, each tile labelled with the shot's name, the frame and its time. Each shot is drawn through its own camera by the same render path as export (Storm for quality fast, Cycles for final; renderer picks by name; neither, when every shot's Quality is Stylized: stylized). Use it to compare shots side by side, check a cut's two ends or a whole sequence's framing, before look_frame on one of them. An unknown shot fails, listing the document's shots. `notes: true` ends the reply with measured notes (e.g. too dark or blown out, a subject cut by the frame, something floating or sunk): `Notes (n): [id] what (when) | …`. Off by default; judge the picture yourself.

- `shots`: Shot ids or names (as the Shots list shows them), in the order of the rows. Default: every shot of the document.
- `count`: Frames in each row, evenly spaced from the shot's first to last frame (a shot with fewer frames gives every row that many).
- `width`: Width of each tile in px; a tile's height follows its shot's own shape.
- `quality`: fast = Storm, the live preview (a few tenths of a second a frame), final = Cycles (path traced, what export gives). Not given on a shot whose Quality is Stylized: the stylized look.
- `renderer`: Overrides quality: storm, cycles or stylized (the stylized look: materials' Lines, Halftone and Light to colour, every other material plainly lit by the scene's real lights; guide materials).

## look_frame what "material"

One material of the document shown on a ball (or a flat square) as a small turntable: `count` angles in ONE strip, under the SCENE's own lights (the document's lights, its sky; everything else hidden), not a studio. Drawn with Storm unless the material needs Cycles (glass / transmission, metal, clear coat, Final-only settings): then Final is picked for you, and the reply says which renderer drew it and why (ask quality fast to force Storm). Use it to judge a material's look, how its highlight travels, before putting it on a shot. A material with blocks (graph.add / graph.connect) is drawn with them, and the reply lists its blocks and wires (`blocks`: graph.describe's blocks and wires), as bright in Storm as in Final under bulbs, spots and panels. An unknown material fails, listing the document's materials; a scene with no light fails (the ball would be black).

- `material`: The material's id or name.
- `shape`: ball = a sphere; plane = a flat square lying face up (to see a texture, grain or a brushed direction).
- `count`: Angles around it, evenly spaced, the first the way the shot camera sees it.
- `radius`: Ball radius (or half a plane's side) in metres; it sits where the shot camera's view meets the ground.
- `width`: Width of each (square) picture in px.
- `quality`: fast = Storm, final = Cycles. Default: Cycles when the material needs it (glass, metal, coat, Final-only settings), else Storm.
- `renderer`: Overrides quality.

## look_frame what "paint"

A mesh's or clay's paint canvas as a picture: the flat paint picture (paintSize square) the renderer lays on its unfolded surface, every layer together, one `layer` or one `channel`; transparent (unpainted) shows as a checkerboard. `zoom` a box and `grid` labels canvas pixels, the coordinates of stroke.add's `points`. A clay's anchored strokes and strokes From the view are shown laid, as the render gets them. Where a canvas spot is on the shot: look_frame what "where".

- `target`: The mesh's or clay's id.
- `zoom`: [x0, y0, x1, y1] box in canvas px. Default: the whole canvas.
- `grid`: Grid spacing in canvas px, labelled. 0 = no grid. Default: chosen to fit.
- `sampling`: How a zoom enlarges: pixels (sharp squares, to place strokes), smooth (to judge edges); auto = pixels with a grid.
- `layer`: Show only this paint layer (its id).
- `channel`: Show only the layers painting this channel (colour, roughness, height = Relief, metal, glow).
- `width` (was `size`): Picture width in px.

## inspect_paint_strokes

Where each stroke of a mesh or clay (or of one paint layer) landed and how far off, one plain line each: "stroke s3 (From the view, layer paint_1): landed on case and lid, at most 1.2 screen px outside the line". A stroke on the surface (canvas `points`, or a clay's `anchors` laid as the render lays them) is measured on the canvas: how far its paint's centre sits from its path, in canvas px (landed = within a tenth of the brush, at least 2 px). A stroke From the view is measured by where its paint shows through its own camera (every pixel of the item whose canvas spot it painted, so paint that also shows somewhere else counts): how far outside the line you drew it shows (screen px; offPx the worst, offMedianPx), in how many separate pieces (pieces; wantPieces: the line's own on that item) and how much of the line it covers (covered, 0..1). It says "landed" only when none shows more than max(3 px, a quarter of the brush) outside the line, at most 2 more pieces than the line has, covering at least 80 % of it; otherwise what went wrong: "painted in 30 pieces, up to 49 screen px outside the line on lid". Each row has the canvas px box and uv box.

- `target`: A mesh's or clay's id (every layer), or one paint layer's id.

## look_frame what "coverage"

How much of each paintable mesh and clay the shot's camera sees is painted, at a frame: "lid: 62 % painted (41 000 of 66 000 px seen)", a spot counting as painted where any shown layer's paint is at least half opaque (as the screen's count), and a picture of the frame with what is seen but unpainted hatched orange (the screen's coverage tint). Paint where the hatch is: look_at there gives the uv. An item seen without surface coordinates (a mesh never unfolded) can't be painted until mesh.unfold.

- `width`: Width of the shot's picture in px (the height follows the shot). Default 960.

## look_frame what "where"

The reverse of look_at: where a spot of a mesh's or clay's paint canvas (`px` canvas pixels, or `uv`) is on the shot's picture at a frame and in the world. Seen: its pixel in a `width` picture, the world point (metres), the distance and the surface direction there. Not seen (behind something, facing away or out of frame): says so, with the nearest pixel where the item is seen and how far that is on the canvas.

- `target`: The mesh's or clay's id.
- `width`: Width of the shot's picture in px (the height follows the shot). Default 960.
- `px`: [x, y] canvas px of the item's paint picture.
- `uv`: [u, v] on the item's unfolded surface (instead of px).

## look_frame what "shape"

An item's FORM, not a lit picture: its outlines from the front (+Z, its left on the picture's right), the side (from its left, +X: its front faces left) and the top (its front down), on one scale with a scale bar and lines at each tenth of its height; plus its measures in numbers, in its own space (metres, before the item's scale): height, width, depth, the width and depth at 10 %, 20 % … 90 % of its height (and in how many parts it is cut there: two legs = 2), the widest, the left-right difference (the front outline against its mirror across its own X = 0, where it is off) and, on a clay, thin spots (where its middle is thinner than ~4 grains: a fragile neck, a wrist that will break up). A clay is measured from its rest shape (the pose isn't measured); a mesh from its built mesh. Use it to check proportions and symmetry in numbers after building, before lighting.

- `target`: The id of the clay or mesh to measure.
- `cells`: A clay: how finely it is sampled along its longest side (more: finer outlines and thin spots, slower).

## render_still

One final picture of a shot through the shot camera (the shot's render Quality by default: Cycles, or Stylized when the Quality is Stylized), as a project render with a manifest: png (sRGB, through OpenColorIO) and/or exr (scene-linear, for the Editor; its passes as named layers, listed in the manifest's `exr`). The file is always written, under the name asked. `notes: true` ends the reply with measured notes (too dark or blown out, a subject cut by the frame, something floating or sunk): `Notes (n): [id] what (when) | …`; off by default. It waits for its file and answers once, finished (a long one answers before your program would give up, says how far, and inspect_job waits again; `wait: false`: the job id at once); inspect_job's note shows how far Cycles has got and the time left measured on this frame ("drawing 40% · about 12 s left").

- `quality`: final = Cycles (path traced), fast = Storm (a draft). Default: the shot's render Quality (Stylized there renders Stylized, every other Quality renders Final).
- `renderer`: Overrides quality: storm, cycles or stylized (materials' Lines, Halftone and Light to colour; drawn at twice the size and smoothed down; no passes).
- `width`: Picture width in px. Default: the shot's render size (renderSize); the height follows.
- `samples`: Cycles samples per pixel. Default: the shot's render quality (draft 32, good 128, final 512).
- `denoise`: Cycles noise clean-up. Default: the shot's render settings (on).
- `exposure`: Stops, applied to the PNG only (the EXR stays scene-linear).
- `passes`: Layers of the EXR beside the picture (Beauty, always): light, reflections (with either, rest = glass, glow and sky, so light + reflections + rest = the picture before noise clean-up), shadow (0 lit .. 1 in shadow; renders each frame twice), masks (one per item, named by its id), depth (metres from the camera), normal (surface direction). Cycles only. Default: the shot's own Passes (Beauty + Masks); [] = Beauty alone.
- `formats`: png = 8-bit sRGB picture, exr = scene-linear half-float for the Editor.

## render_video

An mp4 (H.264, bt709) of a shot, or of a time range of it, through the shot camera: every frame is rendered (the shot's render Quality by default: Cycles, or Stylized when the Quality is Stylized; quality fast = Storm for a draft), then encoded by ffmpeg, plus a small share copy `<name>-share.mp4` beside it (about 8 Mbit/s at 1920×1080, scaled by the picture's size). A project render with a manifest; `exr` keeps the EXR frames too; `output_folder` (+ `file_name`) also copies the mp4 and its share copy there. A stopped or failed render keeps the frames it finished: the same call again (nothing rendered changed) continues from them and draws only the missing frames; the reply says "Continues from N finished frames". It waits for its file and answers once, finished (a long one answers before your program would give up, says how far, and inspect_job waits again; `wait: false`: the job id at once); inspect_job shows 'frame n of m'. With `budget_min` or `estimate_only` the reply waits (up to 25 s) for the measured estimate: over the budget it is an error at once that names the settings that fit, and `estimate_only` returns the figures (never a failed job), also when over the budget. With no quality, renderer or samples it never renders lower than your last export of this shot (a refine keeps the first video's Cycles and samples even if the shot's Quality is lower) and says so; asking for lower is done, and the reply says what it loses (Storm: no fabric sheen, no soft bounce light). The video is always written, under the name asked. `notes: true` ends the reply with measured notes on the first, middle and last frame (too dark or blown out, a subject cut by the frame, something floating or sunk): `Notes (n): [id] what (when) | …`; off by default.

- `quality`: final = Cycles (path traced), fast = Storm (a draft). Default: the shot's render Quality (Stylized there renders Stylized, every other Quality renders Final).
- `renderer`: Overrides quality: storm, cycles or stylized (materials' Lines, Halftone and Light to colour; drawn at twice the size and smoothed down; no passes).
- `width`: Picture width in px. Default: the shot's render size (renderSize); the height follows.
- `samples`: Cycles samples per pixel. Default: the shot's render quality (draft 32, good 128, final 512).
- `denoise`: Cycles noise clean-up. Default: the shot's render settings (on).
- `exposure`: Stops, applied to the PNG only (the EXR stays scene-linear).
- `passes`: Layers of the EXR beside the picture (Beauty, always): light, reflections (with either, rest = glass, glow and sky, so light + reflections + rest = the picture before noise clean-up), shadow (0 lit .. 1 in shadow; renders each frame twice), masks (one per item, named by its id), depth (metres from the camera), normal (surface direction). Cycles only. Default: the shot's own Passes (Beauty + Masks); [] = Beauty alone.
- `start`: Seconds from the start of the shot. Default 0.
- `end`: Seconds from the start of the shot (the frame at this time is the last one). Default: the last frame of the shot.
- `exr`: Also keep every frame as scene-linear EXR next to the mp4 (what the Editor wants), with its passes as layers (passes).
- `output_folder`: A folder (absolute path) to copy the finished mp4 and its share copy into, besides the project render. Made if missing; checked before rendering: a folder that can't be written fails at once.
- `file_name`: The copy's name in output_folder (".mp4" optional; its share copy is <name>-share.mp4). Default: the render's own name. A file already there is replaced.
- `budget_min`: Minutes you can spend. The time is measured first (render_estimate's probe, kept for the scene); it renders either way, and if the estimate is over this the reply says so at once, naming settings that should fit, each with its time.
- `estimate_only`: Return the measured estimate (render_estimate's probe of the middle frame, kept for the scene) and render no video.

## inspect_model_file

What a 3D file holds, without importing it: its format, its unit (and whether the file states one), up axis, animation (frames and fps), and its parts (path, type, material, size in the file's units). Use it before import.add to pick the parts you will give other materials or hide; import.add itself scales a file in another unit to metres and lists its meshes as parts.

- `file`: A 3D file an import reads: USD (.usd .usda .usdc .usdz), glTF (.gltf .glb), OBJ, FBX or Alembic (.abc); absolute, or relative to the project folder.
- `detail`: full adds every prim the engine listed (at most 2000).

## inspect_shot

A shot's facts: frame rate, first and last frame, length in seconds, picture size, the shot camera, every camera in the scene with its lens, and how many items and lights it holds. Reads the document; draws nothing.

## look_frame what "exposure"

How bright a shot's frame is, in numbers: the share of pixels blown out (any channel ≥ 254) and crushed to black (all ≤ 2), the mean, 1st and 99th percentile brightness, and which part of a 3×3 grid is brightest and darkest, with the item at the brightest spot. Draws a small picture through the shot camera and looks at it; use it before a final render to catch a blown-out or too-dark shot. Nothing is changed.

- `quality`: fast = Storm at 320 px (about a second), final = Cycles at 320 px, 32 samples, denoised (what export will look like, slower).
- `renderer`: Overrides quality: storm, cycles or stylized (the stylized look: materials' Lines, Halftone and Light to colour, every other material plainly lit by the scene's real lights; guide materials).
- `width`: Width of the measured picture in px.

## render_estimate

How long a render will take, measured on this machine, without starting it: for a shot (its stored render settings: quality, size, frames; any of them overridden here), a still (`frame`), or all shots. The first call for a scene renders a probe (the middle frame at a quarter of the pixels, and once at the real size with few samples, through the same engine path as the real render) and keeps it, so asking again, or changing only samples, size or frames, answers at once; any change to the scene measures again. The per-frame time includes the scene changing from frame to frame (a cloth or fall's stored shape, animation: one extra small frame is timed at the next frame), and is raised when the last full render of the same shot in this project took 10 %+ over its estimate (the reply says "raised ×N"). Returns seconds a frame, the total, how it was measured, its slowest part, the probe picture, and settings that fit `budget_min`. A probe over its 90 s budget stops and says the job is at least that slow. When another job is using the graphics card the reply says so (`gpu_busy`): the figure was measured under that load, so it is slower than a render on a free card (ask again when it is free before lowering quality), and a probe taken then is not kept. A cloth costs little to render (an 18k-triangle drape: about 0.6 s a frame more at 1280×720, 16 samples); samples, size and the lights cost the time. Always a job: ask with inspect_job (wait_s up to 25).

- `quality`: Instead of the shot's own: draft 32 samples, good 128, final 512 (Cycles); stylized = the stylized renderer (lines, halftone, light to colour), 2× supersampled.
- `samples`: Instead of the shot's own (sets quality custom).
- `denoise`: Noise clean-up, instead of the shot's own (sets quality custom).
- `size`: Instead of the shot's own: full, half or double the shot's frame size.
- `start`: Seconds from the start of the shot (with end: a range instead of the shot's own).
- `end`: Seconds from the start of the shot; the frame at this time is the last one.
- `all_shots`: Every shot of the document, each with its own settings, and a total.
- `budget_min`: Minutes you can spend: over it, the reply names one-setting changes that fit.

## edit_place_on what "highlight"

Move and aim a light so its highlight lands on what is at pixel (x, y) of the shot camera's picture (a sun: its lit side faces it). One change in the history. Then look_frame to see it; the reply there says how much is clipped.

- `light`: The light's id (rect, disk, strip, sphere, spot or distant).
- `x`: Pixels from the left of the picture look_frame gave.
- `y`: Pixels from the top.
- `width`: That picture's width. Default 960.
- `fresh`: true: also put it 4 × the item's size away with the starting brightness (a light just added); false: keep its distance and brightness.

## edit_place_on

Stand a mesh on the surface at pixel (x, y) of the shot camera's picture, its base on the surface along the surface's direction there, the way a person places a shape by clicking (an eye on a face). On a clay whose Mirror is on, a point off its middle (farther than the mesh's own half size, so the two don't overlap) also gives the mesh a mirrored copy on the other side ("<mesh>_mirrored", named "<name> (mirrored)") that follows it: edit the original (edits sent to the copy go to it). On a clay the mesh also follows the clay's pose (Follow, followPose): posed later, it moves and turns with the bone nearest it, its copy with its own side's, so eyes stay on a turning head. The reply gives the size a part placed by a click there gets (spotSize, about a sixth of the clay's width at the spot) when the mesh is far from it. One change in the history. Then look_frame to see it.

- `mesh`: The mesh's id (made first, e.g. by run_script, at its size).
- `x`: Pixels from the left of the picture look_frame gave.
- `y`: Pixels from the top.
- `width`: That picture's width. Default 960.
- `mirror`: On a clay whose Mirror is on (and off its middle): also make the mesh's mirrored copy, which follows it. false: no copy.

## inspect_animations

An item's animations as the timeline shows them. Per setting (X, Y and Z of Position are one, a "Move"; Turn X / Y / Z one "Turn"; Scale X / Y / Z one "Scale"; any other field its own): its keys, its stretches (neighbouring key pairs: ids, start, length, ease, preset, from / to) and its line (overlapping animations go on separate lines). Times are document seconds. Ease a stretch with anim.ease (targets: the stretch's ids); move keys with key.set, stretch them in time with key.scale.

- `owner`: The id of the scene item (mesh, group, light, camera, rig …) whose animations to list.

## look_motion

What moves in a shot and how, measured on every frame from the document's evaluated animation (keys, stepped timing, aims, sticks, follows, poses, mirrored copies, exactly as the scene compiler resolves them); nothing is rendered. Per moving item: when it moves, its path (its pivot's world place, first → last, length in metres, and where it is seen on the shot camera's picture in px), its peak speed and the frame of it, and its stops (still stretches between moves, at least 0.25 s). Findings, facts only, no scores: two shapes passing through each other (both named, the frame span and how deep), sudden jumps (a step at least 1 cm and 4× bigger than the frames either side: a teleport or a snap), and an item partly or wholly outside the picture (frame spans; only when that changes: it leaves or comes in). Overlap test: each shape's own box turned and scaled with it (oriented boxes; a ball: an upright box round it; a clay: the box its pieces reach), so a hollow shape counts as full; touching (under 0.5 mm) is not overlap. Hidden items are left out. Short by default: a line a moving item, identical findings one line, passing through first; `items` for just those, `full` for the speed per frame, `frames` for part of the shot. Simulated things: one set to Falls is measured where the shot's stored simulation has it (as the viewport shows it), and checked for passing through like any shape; when the simulation is out of date (the older result is measured) or not computed (they are where their keys put them) the reply says so first and gives no all-clear: run_simulation, wait with inspect_job, then look again. A cloth's folds and each copy of a falling copies item are not measured here (named under not measured). For every falling thing and cloth of the stored result (copies and cloth included) an "On screen" line says over which frames it drops (until it first lands) and how far, how many of those frames the shot camera's picture shows it in and how many it drops outside (above, below, beside), when it enters and lands, or that it starts already at rest (a copies item: judged copy by copy, how many fall, over which frames they start, the median drop and time seen), with the fix when the fall isn't seen well (sim.start_in_view, fallStart); data `fallsOnScreen`. Fails with the reason on an unknown item, fewer than two frames, or nothing moving.

- `frames`: [first, last] frame to measure (the shot's own numbering). Default: the whole shot.
- `items`: Only these items (all of them listed, no limit); passing through is still checked against every shape in the shot.
- `full`: Adds each item's speed per frame (m/s, and px/s on the picture), its jumps and its moving stretches to the data. Default false: a line per moving item.
- `limit`: Without `items`: how many moving items and finding lines to list (default 20); the reply says how many more there are.
- `all`: Every moving item and every finding line, no cap.
- `path`: Instead of the above, one part's path on the picture: an item id or a clay joint `"buddy.hand.L"` (the bone's end: a hand's tip, an arm's elbow). Per sample its place x, y (0–1 of the picture, 0, 0 top left; behind the camera: null) and on-screen speed (picture heights per second); travel (picture heights), x / y range, peak speed, samples outside the picture. `from_s`, `to_s` (seconds from the shot's start; default the whole shot), `step_s` (default a frame). `view` (as look_frame's, placed at the middle time and held still) measures from there. `picture` (default true): a quick frame at the middle time with the trail drawn on it (line and dots per sample, the bigger dot this frame); `false` = numbers only, no render.

## inspect_voice_lines

The voice lines of the project's RostrumSound songs: id ("<song>/<line id>", what lipsync.make takes as `line`), the words, where the line starts in seconds, and whether its voice is made yet (a line without a voice can't be lip-synced: Make voice in RostrumSound). Also lists the mouths of this scene (groups whose children are named as mouth shapes) and the shape each child stands for.

## render_send_shot

Send a shot to 2D: its render of the scene as it is now becomes a 3D render layer in a 2D scene (one step in that 2D document's history, seen live by an open 2D window), linked by content: 2D marks it "out of date" when this 3D document changes, and a re-send (a new render) clears it. Sending again keeps the same layer and what a person did to it in 2D. With no current render the job renders the shot first (render_video with EXR frames; the shot's own render settings unless quality / width / samples are given). Always a job: ask with inspect_job. Returns the link (2D item, scene, layer) and the render used.

- `target`: 2d = a 3D render layer in a 2D scene. editor: not built yet (fails).
- `scene`: The 2D scene: "<2D item>/<scene id>" or a scene id. Default: the scene this shot was sent to before, else the project's only 2D scene.
- `quality`: final = Cycles (path traced), fast = Storm (a draft). Default: the shot's render Quality (Stylized there renders Stylized, every other Quality renders Final).
- `width`: Picture width in px. Default: the shot's render size (renderSize); the height follows.
- `samples`: Cycles samples per pixel. Default: the shot's render quality (draft 32, good 128, final 512).

## edit_import_asset what "sources"

The asset library's sources of free models: each one's id, name, licence (CC0: free to use, no credit needed) and web site, and whether it is on. Every source is off until the person switches it on in Import › Asset library; you can't switch one on (ask the person). Nothing is fetched from a site while its source is off.

## edit_import_asset what "search"

Search one asset source's models (an on source only; it fails plainly while the source is off). Each result has its id (for edit_import_asset), name and thumbnail address. Nothing is downloaded.

- `source`: The source's id from edit_import_asset what "sources" (polyhaven, ambientcg).
- `query`: Words that must all match the model's name or tags ("chair wood"); empty lists all.
- `page`: Which page of 40 results (0 first).

## edit_import_asset

Bring a model from an asset source into the scene: its files are downloaded into the project folder (assets/<source>/<id>/, reused when already there) and imported with import.add, its base at x y z. One change in the history. Fails plainly while the source is off (the person switches it on in Import › Asset library) or when the download fails (no network, the site said 404 …). Look at the result with look_frame.

- `source`: The source's id from edit_import_asset what "sources" (polyhaven, ambientcg).
- `id`: The model's id from edit_import_asset what "search".
- `x`: Where the model's base (bottom middle) lands: x in metres.
- `y`: Where the model's base (bottom middle) lands: y in metres.
- `z`: Where the model's base (bottom middle) lands: z in metres.

## run_simulation

Simulate a shot: things set to Falls drop, bump and come to rest on things set to Stays still (and the ground, unless the shot's simGround is off), over the whole shot; shapes set to Cloth drape and fold over them (Weight, Stiffness, Air: how much the air slows its fall, a Pinned edge held in place). Set them up first with the sim.body and sim.set operations. Computed once and stored; nothing is computed again until something it depends on changes (a mass, a place, a key). Renders compute it first on their own when it is out of date. Always a job: returns a job id at once; inspect_job shows 'frame n of m'. When done: the stored result's key, frames, how many fell, came to rest and end inside the camera's picture, each cloth's point count and what it ends on (endsOn; a warning when it starts over nothing it can land on, or slides off what it started over), and the engine's time per frame (frameMs). A thing set to Falls with fallStart holds still until then, then falls; in a stream (a copies item's varyStart, or layout pour) each copy is not there until it starts. Whether each fall is seen: onScreen {item: [frames of its drop (until it first lands) the shot camera shows, frames of its drop]}, and a warning when the drop happens above or outside the picture, is on screen under 4 frames, or the thing starts already at rest (a copies item is judged copy by copy: a staggered stream is fine, named only when over a quarter of its copies drop unseen or for under 4 frames), with the fix (sim.start_in_view raises it into the picture; fallStart gives the shot a moment first). A failure names the thing, the frame and what to do (e.g. it starts inside another one: move it up or set Starts: asleep). To nudge the result by hand, the sim.to_keys operation turns it into plain keys (a copies item: keys on every copy, copies.key nudges one); cloth stays a simulation (its folds are not keys). A cloth that tears apart, flies apart or falls past everything fails the same way, naming it and the frame.

## run_simulation what "status"

How a shot's simulation stands: none (nothing falls or is cloth), not computed, stored (up to date) or out of date (something it depends on changed, e.g. a cloth's Stiffness; renders compute it again first), how many things move (each cloth counts one), and any item set to simulate that can't because it sits inside a group or copies.
