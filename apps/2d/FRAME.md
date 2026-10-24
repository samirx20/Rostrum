# The frame (the 2D camera)

Every scene has exactly one **frame**: the box the export shows, and the scene's camera. It sits on the scene's
unlimited canvas (the *world*), and it can be moved, zoomed and turned, each keyable like any layer's setting. It comes
with the scene, starts at **home** and still: then every layer shows exactly as placed, and the export is what it was
before frames existed. The full design (screens, actions, agents' eyes) is the camera spec,
`C:\Users\Sam\.rostrum\waves\results\2d-camera\SPEC.md`; this file is the document, the maths and the engine.

Every top-level layer has a **depth**: how far behind the frame's plane it sits. When the frame moves, near layers move
more and far layers less (parallax). A layer **Pinned to frame** (`screenLock`) moves with the frame, not the world: a
title, a border, a logo bug.

Code: Python `apps/2d/python/rostrum2d/frame/` (`fields.py` the fields, `view.py` the maths, `fit.py` framing,
`rules.py` what is refused, `make.py` a new frame, `convert.py` + `shots.py` + `split.py` older files), the framing
operations `ops_frame_fit.py` (script side `script_frame.py`); engine
`apps/2d/engine/render/src/frame/mod.rs`.

## The document

The frame is a layer of **type `camera`** (the word `frame` is a drawing's frame in this document), the **first** of its
scene's `layers`. Its id is `frame`, or `<scene id>-frame` when `frame` is taken (ids are one per document); code finds
it by its type (`frame.view.of`), never by its id.

| Field | Meaning |
|---|---|
| `x`, `y` | The world point at the frame's centre. Home = the output's centre (960, 540 in 1920 × 1080). |
| `zoom` | 1 = as placed, 2 = twice as close. Above 0. |
| `rotation` | The frame turns clockwise, in degrees, so the picture turns the other way. |
| `homeX`, `homeY` | Where the frame's centre was when the scene was made (the output's centre then). Never keyed; written with the scene and by the conversion, changed by nothing else (see *Changing the size*). |
| `ridePath`, `rideAt`, `rideAlong`, `rideTurn` | The frame rides a path layer as any layer does (`layer.ride`): its centre sits on the path, `x`, `y` an offset from there. |
| `locked` | Drags and operations refuse to move it. |
| any top-level layer: `depth` | 0 = on the frame's plane (moves fully). 1 = twice as far (half as much). Below 0 = nearer. Above −1. Keyable. |
| any top-level layer: `screenLock` | Pinned to frame: its `x`, `y` are in the frame's own px. |

`x`, `y`, `zoom`, `rotation` and `rideAlong` are keyed with the one animation model. A **cut** is a jump: a key with
the `hold` ease, then the next key (the screen will call that ease *Jump*). Keys may sit on shared markers
(`"#reveal-0.033"`), so a cut moves with its marker.

**Refused**, naming the item and field: no frame or two in a scene (so the frame can't be deleted or a second added);
a frame inside a group or rig; effects or masks on it; `depth`, `screenLock`, `start`, `end`, `hidden` on it (it has no
such fields); a zoom of 0 or less in its still value or any key (and, at the frame where it happens, an ease swinging
through 0); a depth of −1 or less. `layer.remove` refuses the frame by name (it keeps the frame among its targets: the
screen picks what that operation takes); the other layer operations that never apply to it (add, duplicate, rename,
arrange, group, mask, effects, paste, shift, trim, stagger, paste style) take `fields.PLACED`.

**Scripts:** `f = frame()` is the current scene's frame (made with `comp()`); `f.key(...)`, `f.set(...)` as any item;
`f.fit(["hills", "tree"], at=4)`, `f.fit(rect=(x, y, w, h), at=4)`, `f.cut(at=6, to="rect", rect=(3200, 0, 1920, 1080))`,
`f.cut(at="#logo lands")`, `f.home(at=8)` run the operations below on the script's tree.
`camera("cam", x=…)` (an older script) is the frame too; `camera(…, start=…, end=…, marker=…)` is refused with how to
write a cut. A re-run never wipes a frame key a person dragged (the document rule).

## Framing and cuts

Three operations on the frame (target: the frame's id, `"frame"`), each one change = one undo step. `at` is
composition seconds (the playhead) or a shared marker (`"#logo lands"`, `"#drop+0.2"`): a key written on a marker
stays on it, so moving the marker moves the framing or the cut.

| Operation | Args | Does | Valid when |
|---|---|---|---|
| `frame.fit` | `to` `view` / `rect` / `items`; `rect` `[x, y, w, h]` world px (the screen sends its visible view); `ids` (layers); `at` (default 0); `pad` (share of the output per side: 0.05 for layers, 0 for a rectangle); `keepRotation` (default true); `cut` (true = `frame.cut` with this `to`) | A rectangle: the largest output-shaped box inside it, turned as the frame is. Layers: the frame that shows them as they will look **in the export at `at`**, depth counted (a far layer moves less, so the frame goes further), as close as `pad` allows, centred (`frame/fit.py`). | not locked |
| `frame.cut` | `at` (required, at least one frame after 0); optional `to`, `ids`, `rect`, `pad`, `keepRotation` as `frame.fit` | x, y, zoom, rotation each get the place the frame has one frame before `at`, keyed there with the `hold` ease (the screen's *Jump*), and at `at` the same place, or with `to` the new one (the jump and the next shot in one step). On a marker the key before is the marker minus one frame (`"#logo lands-0.033333"`). | not locked |
| `frame.home` | `at` (default 0) | x, y back to home, zoom 1, rotation 0: a still field changes, an animated one gets a key at `at`. Refused when the frame is already home there. | not locked, and the frame is away (fact `frameAway`: keyed, or still off home) |

**The keying rule of a fit:** x, y and zoom (and rotation when the turn isn't kept) get a key at `at`; a field with no
keys yet is also keyed at 0 s with its value now, so the frame starts where it was and arrives there. At 0 s with no
keys the still values just change (the frame moves for the whole piece). A fit or cut on a field driven by an
expression, on a frame riding a path, with a locked or pinned layer, unknown or no `ids`, a rectangle with no area, or a
zoom outside 0.01 to 100 is refused, naming the item and field.

**Status words:** the operations return nothing; `ops_frame_fit.words(op, frame, args, t)` (the frame as it is before
the call, `t` = `at` in seconds) gives the screen's line: "Frame keyed at 0 s (where it was) and 3 s", "Cut at 2.40 s.
Move the frame to the next shot.", "Frame home".

### Changing the size

Until the screen brief that resizes about the frame (spec F7, § 4.13): a frame that never left home (no keys, no ride,
at home, home at the old output centre) moves its centre and home to the new output centre (`frame/make.py` `resized`,
from `comp.set` and `comp.size`), so the picture stays the scene's top-left width × height, as before frames; a frame
that was moved or keyed keeps looking where it looked and keeps its home. (`value.set` on a scene's width doesn't
run this rule; `comp.set` and `comp.size` do.)

## The maths

O = the output's centre (width / 2, height / 2), H = home, F = the frame's centre (x, y), z = zoom, roll = rotation,
s = 1 / (1 + depth). A point p of a top-level layer (world px) shows in the **export** at

    out(p) = O + R(−roll) · zˢ · (p − H − s · (F − H))

- At home (F = H, z = 1, roll = 0) with H = O: out(p) = p, every layer as placed.
- depth 0: out(p) = O + R(−roll) · z · (p − F), the plain frame. A pan by d moves a layer by s · d the other way.
- Pinned: out(q) = q (q in the frame's own px).
- The old camera's maths is the case H = O (every converted file).

The **world view** (the canvas outside Look through, spec § 8.3) draws a layer where the export shows it, carried back
through the plain frame: world(p) = F + z^(s−1) · (p − H − s · (F − H)) (pinned: F + R(roll) · z⁻¹ · (q − O)). Depth 0
and a frame at home: world(p) = p. `frame/view.py` `layer_matrix` and `world_matrix` give both as 2D matrices, `undo` the
inverse (a drag turned back into a layer's own values).

The engine draws the world view on request (`frame` with `world {x, y, w, h, scale}`, ENGINE_CONTRACT.md § 1;
`render/src/scene_world.rs`): the stage written with the world maths (`View::world`, `scene/stage.rs` `world_parts`), so
page px are world px, painted over that rectangle with what lies wholly outside it culled (blitz-paint `set_viewport`)
and the stage's clip at the frame lifted for that paint only (serve.rs `open_stage`). The frame's quad is filled with the
export of the same time, drawn in a second set of surfaces (painter.rs `swap_aside`) at the size it is shown, starting on
a whole device pixel when the frame is upright, and laid in (`draw_over`, the world paint leaving the quad alone:
`clip_out`). A frame at home and not motion-blurred needs no second pass (inside the frame the world page equals the
export); a rectangle inside an upright frame is the export's crop alone. Proved: inside the outline equals the export
(`python/tests/test_world_picture.py`); exports after a world picture are byte for byte (Lull, 24 frames).

The engine writes the export matrix as a wrapper around each top-level layer:
`<div id="cam~<layer id>" style="…transform-origin:0 0;transform:matrix(a, b, c, d, e, f);<blend>">`, carrying the
layer's blend. The wrappers are written for every top-level layer **when the frame ever leaves home** (a key on x, y,
zoom or rotation, a ride, a still value away from home, or H ≠ O; `leaves_home`, the same rule in Python and Rust),
decided from the scene, so the page keeps its shape from frame to frame (keep.rs); **never otherwise**, so a scene
whose frame stays home writes byte for byte the page it wrote before frames.

**Motion blur** never crosses a jump: a shutter sub-frame reads each field on the frame's own side of any hold key
between them (MOTION.md › No blur across a jump), so a cut never smears two shots.

## Older files

Opening a file of format 2 or older converts it in memory (format step 2 → 3, `rostrum2d/migrations.py` →
`frame/convert.py`), before the document is checked; it is written in the new format at the next save. The step reads
the project's shared markers (format steps may take the project folder, as `upgrade` does). The history records it as
one change by "Rostrum (older file)", with what it did in words.

1. **No camera:** the frame at home, still. The engine writes no wrappers: the export is byte for byte the same
   (proved on 8 scenes, 1,080 frames, 2026-10-24).
2. **One camera showing for the whole scene, not timed on markers:** its fields, keys, expressions and ride move to
   the frame (key ids follow the frame's id). Pictures identical.
3. **Several cameras, one that doesn't show all the time, or cameras timed on markers:** the frame's track is built
   shot by shot (`frame/shots.py`). At each frame the camera showing is the later one in the list (the old rule); no
   camera showing holds home. For each shot, the camera's keys inside it are copied, a key starts it with the value it
   has there, and its last key gets the `hold` ease (the cut). A move a cut falls inside is split exactly: a linear or
   hold stretch as it is, a curve ease (named or custom) as the exact part of its curve (`frame/split.py`, a custom
   ease); a spring, a bounce, a bent path, a repeating key or a riding camera get a key per frame there, said in the
   label. A shot whose camera was timed on a marker gets its keys, and the cut into it, on that marker. Expressions on
   the cameras are left out (said); a marker the project lacks reads as 0 s (said).
4. Expressions elsewhere that read an old camera's field (`cam.x`) read the frame's.

Lull (six cameras on markers, 600 frames): with motion blur off, 587 frames byte-identical and 13 within 18/255 on a
few antialiased pixels; with blur on, the frames next to each cut differ because the blur no longer smears the two
shots.

## Agents' eyes

- **Frames, contact sheets, video, `boxes`, `place`**: drawn through the stage, so they show the export.
- **`look_at`** (its reply's `frame`: x, y, zoom, rotation), **`look_frame`'s list**, **`look_motion`**
  (`mcp/geometry.py`): boxes are where the layer shows in the picture, through `frame/view.py`.
- **`look_rig`**: the `bones` reply gives each rig's frame matrix as `frame`; **`inspect_rig_motion`** undoes it.
- **`look_path layer=frame`**: the frame's path from its keys; motion samples list it as `camera:<frame id>`.
- **Lottie**: a frame that never leaves home writes nothing extra; one that moves is baked into one null per depth,
  a cut as a hold keyframe (`io/lottie_camera.py`).
