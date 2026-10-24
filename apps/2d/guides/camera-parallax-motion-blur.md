# Camera, parallax and motion blur

Tools for a camera that moves over the composition, layers that sit at different distances, and for showing speed:
motion blur, smears and trails. Read `start-here` first. Exact maths: `apps/2d/CAMERA.md` and `apps/2d/MOTION.md`.

## The camera

A **camera** is a layer of the composition that is never drawn. It decides which part of the composition the screen shows.
Make one in a script with `camera("cam")`, or `layer.add type=camera`.

| Field | Does |
|---|---|
| `x`, `y` | The composition point shown at the centre of the screen. The composition's centre (960, 540 in 1920 × 1080) = at rest. |
| `zoom` | 1 = as placed, 2 = twice as close. Must be above 0. |
| `rotation` | Roll in degrees; the camera turns clockwise, so the picture turns the other way. |
| `start`, `end` | From when to when this camera is the one used. Several cameras with different times make cuts; if two show at once, the one higher in the layer list wins. |

All but `start` / `end` can be keyed like any field:

```python
cam = camera("cam")
cam.key("x", {0: 760, 4: 1300}, ease="easeInOut")      # a pan
cam.key("zoom", {1.5: 1, 4: 1.35}, ease="easeInOut")   # a push in
```

**On the canvas.** The canvas shows the picture through the camera. Pick the camera (its row is pinned at the top of
the layers) and you see its moves: its path (where it looks, one dot per frame), a faint frame at each of its keys (what
it will show there; a push in draws smaller frames), and its keys as squares. Drag a square to move where the camera looks
at that key (one undo step; it snaps to the frame's edges and centre, **Ctrl** or **Alt** frees it); click a square and drag its handles to curve the move. So a camera push along a curve is
two or three keys and a few drags, no typed numbers. The faint path and frames also show while something else is picked;
switch them off with **Camera frame** in the **Fit · %** menu (a view setting, not saved in the project).

A camera can also ride a path layer beside it: `layer.ride target=cam path=road at=along`, then key `rideAlong` 0 → 1.
Where it looks sits on the path, its own `x` / `y` become an offset, and `turn=true` rolls it with the path's direction
(see `shape-and-path-animation`).

No camera showing (between cameras, or none at all): every layer is drawn exactly as placed. A camera cannot sit inside a group
or rig, and cannot have effects or masks; a zoom of 0 or less is refused, even where an ease swings past a limit.

## Depth and parallax

Each **top-level** layer of the composition has:

| Field | Does |
|---|---|
| `depth` | How far behind the camera's plane. 0 = on it (moves with the camera fully); 1 = twice as far (moves half as much); 3 = a quarter; below 0 = nearer (−0.5 moves twice as much). Must be above −1. Animatable. |
| `screenLock` | The camera doesn't move, zoom or turn it (a title, a frame, a logo bug). On the screen: **Pinned to screen**. |

```python
shape("hills", shape="rect", w=2400, h=500, x=960, y=900, depth=3)       # far: moves little
text("title", body="…", size=120, x=960, y=200, screenLock=True)         # stays put on screen
```

A pan by d moves a layer by d / (1 + depth) on screen the other way; far layers also grow less on a push-in. Inside a group
or rig a layer follows its group: put the **group** at a depth. `depth` and `screenLock` apply only to a composition's own
layers in a composition with a camera (anything else refuses them: without a camera they would do nothing); on the
screen the **Depth** group shows only then.
Layers are flat: for a layer that turns in perspective use `tiltX` / `tiltY` (see `ui-and-product-animation`).

## Motion blur (shutter)

Two fields on the **composition** (set with `comp.set`, or `comp("main", shutter=180)`; not animatable). On the screen:
pick the scene, click **+ Motion blur**: it is on at 180° (**Amount**), with **Blur steps** under it; **−** turns it off.

| Field | Does |
|---|---|
| `shutter` | Shutter angle in degrees of a frame. 0 = no blur (default); 180 = half a frame; 360 = a whole frame. |
| `shutterSamples` | How many moments inside the open shutter are averaged (2–64, default 8). More is smoother on fast moves and takes about that many times longer per frame. |

The frame at time t is the average of the samples centred on t. Layers that do not move stay sharp. Motion of keys, groups,
rigs and the camera all blur. Preview and export blur the same way. If the steps show on a very fast spin or whip, raise
`shutterSamples`.

## Smear and trail (effects on a layer)

Both read the layer's **real** motion. Add with `effect.add type=smear` / `type=trail`, or `layer.effect("smear", id="s", ...)`.

| Effect | Field | Does |
|---|---|---|
| `smear` | `amount` | Stretch per px moved; 1 = a move of its own length in one frame doubles it. |
| | `max` | The most it stretches, times its length. |
| | `minSpeed` | px per frame under which it does not smear. |
| | `stretch` | `behind` (front edge stays, smear trails back) or `both` (about the anchor). |
| | `keepArea` | Gets thinner across the move as it lengthens. |
| `trail` | `copies` | How many echoes (1–32, not animatable). |
| | `spacing` | Frames between echoes. |
| | `fade` | Each echo's opacity = the one before × this. |

A smear reads the layer's **own** motion: a layer that only moves because its group moves does not smear; put the smear on
the group. Text length is estimated (0.6 × size per letter) before layout; `amount` tunes it.

## Seeing and checking

- `look_frame` at the fastest moments shows the blur, smear and echoes; `look_sheet` over the move shows how they grow and settle.
- `look_at x y time`: with a camera, boxes are where the layer shows **on screen** through the camera.
- `look_path layer=cam` (or any layer): the path it travels, sample by sample: its own x / y and where it shows on
  screen, its keys with their handles, the path's length and its top speed.
- `look_motion`: facts from each layer's own keys, the camera's included; it does not add the camera's motion to other layers.
- `look_rig`, `inspect_rig_motion`: skeletons are drawn where the character shows; the foot-slide check undoes the camera so a
  moving camera is not read as a slide.

## Not yet

Handheld shake or camera noise, a look-at target that follows a layer (it can ride a path, see "A layer riding a path" in `shape-and-path-animation`), depth of field, a camera with perspective in depth (depth is parallax
scaling, not 3D).
