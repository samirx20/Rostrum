# The frame (the camera), parallax and motion blur

Tools for a shot that moves over the scene, layers that sit at different distances, and for showing speed: motion
blur, smears and trails. Read `start-here` first. Exact maths: `apps/2d/FRAME.md` and `apps/2d/MOTION.md`.

## The frame

Every scene has exactly one **frame**: the box that is exported, and the scene's camera. It comes with the scene (you
never add or delete it) and starts at **home**, still: then every layer shows exactly as placed. In the document it is
the scene's first layer, of type `camera`, id `frame` (in a second scene `<scene id>-frame`).

| Field | Does |
|---|---|
| `x`, `y` | The point of the scene at the frame's centre. Home = the output's centre (960, 540 in 1920 × 1080). |
| `zoom` | How close the frame looks: 1 = as placed, 2 = twice as close. Must be above 0. |
| `rotation` | Turns the frame clockwise in degrees, so the picture turns the other way. |
| `homeX`, `homeY` | Where the frame's centre was when the scene was made. Written with the scene; never keyed. |
| `locked` | Drags and operations refuse to move the frame until it is unlocked. |

`x`, `y`, `zoom` and `rotation` can be keyed like any field:

```python
f = frame()                                           # the scene's frame, made with comp()
f.key("x", {0: 760, 4: 1300}, ease="easeInOut")       # a pan
f.key("zoom", {1.5: 1, 4: 1.35}, ease="easeInOut")    # a push in
```

From an agent: `value.set target=frame prop=x v=1300 at=4` (a key at 4 s once the field has keys), or `key.add`.

**A cut** is a jump of the frame from one place to another on one frame: a key with the **hold** ease, then the next
key. `f.key("x", {2.4: (960, "hold"), 2.5: 3200})` holds the first shot until 2.5 s and jumps there. Key times can sit on
a shared marker (`"#reveal"`, `"#reveal-0.033"`), so moving the marker moves the cut. Motion blur never crosses a cut.

**On the canvas.** The canvas shows the picture through the frame. Pick the frame (its row is pinned at the top of
the layers) and you see its moves: its path (its centre, one dot per frame), a faint outline at each of its keys (what
it will show there; a push in draws smaller outlines), and its keys as squares. Drag a square to move the frame at
that key (one undo step; it snaps to the picture's edges and centre, **Ctrl** or **Alt** frees it); click a square and drag
its handles to curve the move. So a push along a curve is two or three keys and a few drags, no typed numbers. The
faint path and outlines also show while something else is picked; switch them off with **Camera frame** in the
**Fit · %** menu (a view setting, not saved in the project).

The frame can also ride a path layer beside it: `layer.ride target=frame path=road at=along`, then key `rideAlong` 0 → 1.
Its centre sits on the path, its own `x` / `y` become an offset, and `turn=true` rolls it with the path's direction
(see `shape-and-path-animation`).

Refused, naming the item and field: deleting the frame, a second frame, a frame inside a group or rig, effects or masks
on it, `depth` or `screenLock` on it, and a zoom of 0 or less (even where an ease swings past a limit).

**Older files** open with their cameras turned into the frame: one camera for the whole scene becomes its fields and
keys; several cameras (or one that doesn't show all the time) become one frame with cuts, each still on its marker.
Old scripts' `camera("cam", …)` gives the frame; `camera(…, start=…)` is refused with how to write a cut.

## Depth and parallax

Each **top-level** layer of the scene has:

| Field | Does |
|---|---|
| `depth` | How far behind the frame's plane. 0 = on it (moves with the frame fully); 1 = twice as far (moves half as much); 3 = a quarter; below 0 = nearer (−0.5 moves twice as much). Must be above −1. Animatable. |
| `screenLock` | **Pinned to frame**: moves with the frame, not the scene (a title, a border, a logo bug); its `x`, `y` are in the frame's own px. |

```python
shape("hills", shape="rect", w=2400, h=500, x=960, y=900, depth=3)       # far: moves little
text("title", body="…", size=120, x=960, y=200, screenLock=True)         # pinned to the frame
```

A pan by d moves a layer by d / (1 + depth) in the picture the other way; far layers also grow less on a push-in. At
home every layer shows as placed, whatever its depth: place far things with the frame where it is when it looks at them.
Inside a group or rig a layer follows its group: put the **group** at a depth (the layer's own `depth` and `screenLock`
are ignored there).
Layers are flat: for a layer that turns in perspective use `tiltX` / `tiltY` (see `ui-and-product-animation`).

## Motion blur (shutter)

Two fields on the **composition** (set with `comp.set`, or `comp("main", shutter=180)`; not animatable):

| Field | Does |
|---|---|
| `shutter` | Shutter angle in degrees of a frame. 0 = no blur (default); 180 = half a frame; 360 = a whole frame. |
| `shutterSamples` | How many moments inside the open shutter are averaged (2–64, default 8). More is smoother on fast moves and takes about that many times longer per frame. |

The frame at time t is the average of the samples centred on t. Layers that do not move stay sharp. Motion of keys, groups,
rigs and the frame all blur, except across a cut (a hold key): no sample crosses it, so two shots never smear. Preview
and export blur the same way. If the steps show on a very fast spin or whip, raise
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
- `look_at x y time`: boxes are where the layer shows **in the picture**, through the frame (the reply gives the frame's `x`, `y`, `zoom`, `rotation`).
- `look_path layer=frame` (or any layer): the path it travels, sample by sample: its own x / y and where it shows on
  screen, its keys with their handles, the path's length and its top speed.
- `look_motion`: facts from each layer's own keys, the frame's included; it does not add the frame's motion to other layers.
- `look_rig`, `inspect_rig_motion`: skeletons are drawn where the character shows; the foot-slide check undoes the frame so a
  moving frame is not read as a slide.

## Not yet

Handheld shake or frame noise, a look-at target that follows a layer (it can ride a path, see "A layer riding a path" in `shape-and-path-animation`), depth of field, a frame with perspective in depth (depth is parallax
scaling, not 3D).
