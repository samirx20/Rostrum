# The 2D camera

A **camera** is a layer in a composition's own layer list that is never drawn. It decides what part of the
composition the screen shows: where it looks (`x`, `y`), how close it is (`zoom`) and how it is turned (`rotation`,
the roll). Every other top-level layer gets a **depth**: how far behind the camera's plane it sits. When the camera
moves, near layers move more and far layers less, which is what makes a flat picture feel deep (parallax). A layer
with **Locked to screen** (`screenLock`) ignores the camera completely: a title, a frame, a logo bug.

A camera can **ride a path layer** beside it, as any layer does (`layer.ride`; `ridePath`, `rideAt`, `rideAlong`,
`rideTurn`, resolved in the engine's `scene/follow.rs`): where it looks sits on the path on every frame, its own `x`,
`y` an offset from there, and with `rideTurn` it rolls with the path's direction. The look tools and the Lottie export
place it with the same ride (Python `follow.ride`, the engine's rule).

Code: engine `apps/2d/engine/render/src/camera/mod.rs`; Python `apps/2d/python/rostrum2d/camera/` (`fields.py` the
fields, `view.py` the same maths for the look tools).

## The document

| Item | Field | Meaning |
|---|---|---|
| camera | `x`, `y` | The composition point shown at the centre of the screen. The composition's centre (960, 540 in a 1920 × 1080 comp) = at rest. |
| camera | `zoom` | 1 = as placed, 2 = twice as close. Must be above 0. |
| camera | `rotation` | Roll in degrees: the camera turns clockwise, so the picture turns the other way. |
| camera | `start`, `end` | When this camera is the one used. |
| any top-level layer | `depth` | 0 = on the camera's plane (moves with it fully). 1 = twice as far (moves half as much). 3 = four times as far (a quarter). Below 0 = nearer than the plane (−0.5 moves twice as much). Must be above −1. |
| any top-level layer | `screenLock` | The camera doesn't move, zoom or turn it. |

All camera fields except `start` and `end` can be keyed, with the one animation model like any other field. So can
`depth`.

- **Cuts.** Several cameras with different `start`/`end` times make camera cuts: at each moment the camera showing is
  used. If two show at the same moment, **the one later in the layer list** (higher in the stack) wins, the same way a
  later layer covers an earlier one.
- **No camera showing** (between cameras, or before the first starts): every layer is drawn exactly as placed.
- **No camera at all** in the composition: nothing changes; the page the engine writes is byte for byte what it was
  before cameras existed.
- **Groups and rigs.** `depth` and `screenLock` only mean something on a composition's own layers. A layer inside a group
  or a rig follows its group (put the group at a depth). Its own `depth` and `screenLock` are ignored.
- **Refused** when the scene loads or is edited, naming the item and field: a camera inside a group or rig; a camera with
  effects or masks; a zoom of 0 or less (still or in any key); a depth of −1 or less. A key whose ease swings past
  a limit between two good keys (a spring zoom going through 0) is refused on the frame where it happens.

## The maths

C is the composition's centre, `cam` = (x, y) of the camera, s = 1 / (1 + depth). A point p of a top-level layer
(in composition pixels) shows on screen at

    screen = C + R(−roll) · zoomˢ · (p − C − s · (cam − C))

- With the camera at rest (looking at C, zoom 1, roll 0) every layer shows exactly as placed, whatever its depth.
- A pan by d moves a layer by s · d on screen the other way: far layers (small s) move less.
- `zoomˢ`: far layers grow less on a push-in.
- The roll turns every layer by the same amount about the screen centre (a real camera rolling turns the whole picture).
- `screenLock`: the identity (screen = p).

It is one 2D matrix per top-level layer. The engine writes it as a wrapper around the layer:
`<div id="cam~<layer id>" style="position:absolute;left:0;top:0;width:100%;height:100%;transform-origin:0 0;transform:matrix(a, b, c, d, e, f)">`.
The wrapper is written for every top-level layer whenever the composition has a camera, even at rest, so the page
keeps the same shape from frame to frame and the kept page only restyles (keep.rs). It also carries the layer's blend
mode (a transformed box holds what is inside it apart, so the blend has to sit on the wrapper to reach the layers
below). Frames, contact sheets and the export all go through the same stage markup (preview ≡ export).

## Scene description (ENGINE_CONTRACT.md § 2, same version)

`{"id": "cam", "type": "camera", "props": {"x", "y", "zoom", "rotation", "start", "end"}, "anim"?: {…}}` in the comp's
`layers`, every field present, no `effects`, `masks` or `layers`. Every layer carries `depth` (number) and `screenLock`
(true/false) with the rest of its transform.

## Operations

There are no camera-only operations: a camera is a layer, so the layer operations add, change, key, reorder and delete
it, through the GUI, a script or MCP, recorded in the one history. In a script:

    cam = camera("cam")                       # at rest: looks at the comp centre
    cam.key("x", {0: 760, 4: 1300})           # pan
    cam.key("zoom", {1.5: 1, 4: 1.35})        # push in
    shape("hills", ..., depth=3)              # far
    text("title", ..., screenLock=True)       # stays on the screen

## Agents' eyes

- **Frames, contact sheets, video, `boxes`**: drawn and measured through the stage, so they show the camera's view.
- **`look_at`, `look_frame`'s list of what shows, `look_motion`'s on-screen checks** (`mcp/geometry.py`): boxes and
  corners are where the layer shows on screen, through the camera (`camera/view.py`, the same maths as the engine;
  `tests/test_camera.py` checks hand-computed points).
- **`look_rig`**: the engine's `bones` request reports bones in screen px through the camera, so the skeleton is drawn
  where the character shows. It also gives each rig's camera matrix (`camera`); **`inspect_rig_motion`** undoes it, so
  a planted foot is measured where it stands in the composition and a moving camera doesn't make it "slide".
- **`look_motion`'s moves and paths** are facts about each layer's own keys (composition px), the camera's included; they
  don't add the camera's motion.
