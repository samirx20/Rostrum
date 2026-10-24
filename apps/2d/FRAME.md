# The frame (the 2D camera)

Every scene has exactly one **frame**: the box the export shows, and the scene's camera. It sits on the scene's
unlimited canvas (the *world*), and it can be moved, zoomed and turned, each keyable like any layer's setting. It comes
with the scene, starts at **home** and still: then every layer shows exactly as placed, and the export is what it was
before frames existed. The full design (screens, actions, agents' eyes) is the camera spec,
`C:\Users\Sam\.rostrum\waves\results\2d-camera\SPEC.md`; this file is the document, the maths and the engine.

Every top-level layer has a **depth**: how far behind the frame's plane it sits. When the frame moves, near layers move
more and far layers less (parallax). A layer **Pinned to frame** (`screenLock`) moves with the frame, not the world: a
title, a border, a logo bug.

Code: Python `apps/2d/python/rostrum2d/frame/` (`fields.py` the fields, `view.py` the maths, `rules.py` what is
refused, `make.py` a new frame, `convert.py` + `shots.py` + `split.py` older files); engine
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

**Scripts:** `f = frame()` is the current scene's frame (made with `comp()`); `f.key(...)`, `f.set(...)` as any item.
`camera("cam", x=…)` (an older script) is the frame too; `camera(…, start=…, end=…, marker=…)` is refused with how to
write a cut. A re-run never wipes a frame key a person dragged (the document rule).

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
