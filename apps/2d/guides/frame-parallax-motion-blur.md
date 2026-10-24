# The frame, parallax and motion blur

Tools for a shot that moves over the scene (the frame is the camera), for looking through it, for titles pinned to it,
for layers that sit at different distances, and for showing speed: motion blur, smears and trails. Read `start-here`
first. Exact maths: `apps/2d/FRAME.md` and `apps/2d/MOTION.md`.

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

**A cut** is a jump of the frame from one place to another on one frame: a key with the **hold** ease (the screen's
**Jump**), then the next key. `f.key("x", {2.4: (960, "hold"), 2.5: 3200})` holds the first shot until 2.5 s and jumps
there. Key times can sit on a shared marker (`"#reveal"`, `"#reveal-0.033"`), so moving the marker moves the cut.
Motion blur never crosses a cut.

**Framing and cutting in one step** (each one change, one undo step; `at` is seconds or a marker such as
`"#logo lands"`, and a key written on a marker stays on it):

| Operation | Does |
|---|---|
| `frame.fit to=view rect=[x, y, w, h] at=3` | The frame becomes the largest frame-shaped box in that rectangle (world px), keeping its turn, keyed at `at`. If the frame had no keys yet, its place now is also keyed at 0 s, so it starts where it was and arrives there. |
| `frame.fit to=items ids=[hills, tree] at=3` | The frame shows those layers as they will look in the export at `at` (depth included), with 5 % room (`pad`). |
| `frame.cut at=2.4` | Two keys: the frame's place one frame before `at` with the Jump ease, and the same place at `at`. Then move the frame to the next shot: that sets the key at `at`. |
| `frame.cut at=2.4 to=view rect=[…]` / `to=items ids=[…]` | The jump and the next shot in one step. |
| `frame.home at=2` | Back home (centre at home, zoom 1, no turn): a still field changes, an animated one gets a key. |

In a script: `f.fit(["hills", "tree"], at=4)`, `f.cut(at=6, to="rect", rect=(3200, 0, 1920, 1080))`, `f.home(at=8)`.

**On the canvas.** The canvas shows the world around the frame; inside the frame is exactly the export. Pick the frame
(**C**, its name tab, or its row pinned at the top of the layers) and drag it: inside moves it, a corner zooms it, just
outside a corner turns it (see [the-screen.md](the-screen.md) part 2). You also see its moves: its path (its centre, one dot per frame), a faint outline at each of its keys (what
it will show there; a push in draws smaller outlines), and its keys as squares. Drag a square to move the frame at
that key (one undo step; it snaps like any dragged thing, **Ctrl** or **Alt** frees it); click a square and drag
its handles to curve the move. So a push along a curve is two or three keys and a few drags, no typed numbers. A cut
shows as a dashed line with no dots. The faint path and outlines also show while something else is picked; switch
them off with **Show the frame's path** in the **Fit · %** menu (a view setting, not saved in the project).

**Framing by clicks.** With the frame picked, the top of the settings panel has **Frame the view** and **Cut here**, and
its **⋯** has **Frame home** (only when the frame is away from home at the playhead) and **Lock**. The same are on
right-click (the Frame row, or the canvas) and in **Ctrl+K**, which also has **Cut to the view**. With layers picked,
**⋯** has **Frame these** and **Cut to these**. Only what applies shows: no Cut here at 0 s, and a locked frame offers
only Unlock.

- **A push:** pick the frame (**C**) at 0 s, move the playhead to 3 s, pan and zoom your view until the second place
  fills the canvas the way you want it, then **Frame the view**. The frame fits what you see (leaving the same room
  round it as **Ctrl+0**) and is keyed at 3 s; the status line says "Frame keyed at 0 s (where it was) and 3 s". Or
  pick the layers you want in the shot and use **⋯ › Frame these**. Then shape the move as any move: drag its key
  squares, bend its handles, ease it in the key bar.
- **A cut:** put the playhead where the cut happens and click **Cut here** ("Cut at 2.40 s. Move the frame to the next
  shot."). Then drag the frame to the next shot, or pan there and **Frame the view**: either sets the key at the
  playhead. Faster: pan to the next shot and **Ctrl+K › Cut to the view**, or pick layers and **⋯ › Cut to these**.
  The cut shows as an orange tick on the Frame row and a dashed path on the canvas. Any frame key can also be made a
  cut by hand: pick it on the timeline and choose **Jump** in the key bar's **Ease** (or press **Ctrl+Alt+J**).
- **On a marker:** with the playhead on a marker (**Alt+M** goes to the next one), Frame the view and Cut here tie their keys to
  that marker. Move the marker on the ruler and the cut moves with it, so RostrumSound can put a hit on it.

The frame can also ride a path layer beside it: `layer.ride target=frame path=road at=along`, then key `rideAlong` 0 → 1.
Its centre sits on the path, its own `x` / `y` become an offset, and `turn=true` rolls it with the path's direction
(see `shape-and-path-animation`).

Refused, naming the item and field: deleting the frame, a second frame, a frame inside a group or rig, effects or masks
on it, `depth` or `screenLock` on it, and a zoom of 0 or less (even where an ease swings past a limit).

**Older files** open with their cameras turned into the frame: one camera for the whole scene becomes its fields and
keys; several cameras (or one that doesn't show all the time) become one frame with cuts, each still on its marker.
Old scripts' `camera("cam", …)` gives the frame; `camera(…, start=…)` is refused with how to write a cut.

## Looking through the frame

The canvas normally shows the world around the frame, with the export inside its outline. To see the export alone:

- **Shift+C**, or **Look through the frame** in the **Fit · 54 % ▾** menu (a check mark shows it is on). The canvas
  fits the frame and shows exactly what is exported, nothing outside it. A small **Through the frame ×** label sits at
  the bottom-left of the canvas; its **×**, Shift+C again, or the menu item turns it off, and your own view (where you
  had scrolled, at the same zoom) comes back.
- Editing still works: pick, drag, type and paint on what you see. A far layer still moves under the pointer. The
  frame itself is the edge of the canvas here, so it has no handles; its settings panel still works.
- Scrubbing while looking through keeps looking through: the canvas follows the frame's move.
- **Playing always looks through the frame**, whether this is on or not; when it stops you are back in the view you had,
  never moved for you. Scrubbing with it off keeps the world view, so you can line a move up against the world.
- It is only your view: never a change, never undone, never saved in the project.

A turned frame is shown turned while looking through (its box fitted, nothing outside it); playing and the export show
it upright.

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
home every layer shows as placed, whatever its depth.
Inside a group or rig a layer follows its group: put the **group** at a depth (the layer's own `depth` and `screenLock`
are ignored there).
Layers are flat: for a layer that turns in perspective use `tiltX` / `tiltY` (see `ui-and-product-animation`).

**On the screen:** pick a layer of the scene (not one inside a group) and open its **Depth** group in the settings
panel. **Depth** sets how far it is; the layer **stays where it shows at the playhead** (its position and size change
with it, as one undo step), so changing depth never makes it jump. For drawings, **Set depth ▾** on the actions row
offers Far / Middle / Near / Other depth…, which also resizes a painted background to cover the frame's move (see
`painted-backgrounds`). The canvas draws every layer as the frame sees it at the playhead, so a far layer slides by its
parallax when you scrub, and you grab it where you see it.

**Place far things with the playhead at the moment the frame looks at them.** A far hill placed at 0 s, with the frame
at home, is right for 0 s; where it shows when the frame arrives at 4 s is the parallax. **Frame these** works depth
out correctly.

From an agent: `layer.set_depth target=[hills] depth=3 at=2` keeps the layer where it shows at 2 s (every key carried
along, so its motion keeps its shape); `keep: "values"` changes only the depth (the layer may jump). In a script:
`set_depth("hills", 3)`. Setting the `depth` field itself (`value.set`, `shape(..., depth=3)`) changes only the number.

## Pinned to frame

A title, a logo bug or a border that belongs to the shot, not the world, is **pinned to the frame**: it moves, zooms
and turns with the frame, and its X, Y are in the frame's own pixels (960, 540 is the middle of the shot).

- **On the screen:** pick it › settings › **Depth** › **Pinned to frame** on, or **⋯ › Pin to frame** (**Unpin from
  frame** when it is pinned). It stays where it shows at the playhead; one undo step. Its row in the layers list gets a
  small pin.
- **In the world view** it rides inside the frame's outline: scrub and it travels with the outline; when the frame
  zooms or turns it is drawn sized and turned with the box. Dragging it moves it within the frame, and it snaps to the
  frame's edges and centre.
- Unpinning works the same way round: it stays where it shows at the playhead and becomes a layer of the world again.
- From an agent: `layer.pin target=[title] on=true at=2` (or `on=false`); `keep: "values"` flips only the switch. In a
  script: `pin(title)`, `pin(title, False)`. Writing `screenLock` itself changes only the switch.
- Pinned layers get no motion blur from the frame's move and no parallax, so **Depth** isn't shown while a layer is pinned.

Refused with `keep: "shown"`, naming the layer: a layer riding a path, a position driven by an expression, and (only
while the frame is turned) X and Y keyed at different times or eases: key them together with **K** first.

## Changing the output size

Scene settings › **Size** (or `comp.size`, `comp.set width / height`): the frame takes the new size **about its
centre**. It keeps looking at the same point of the world; its zoom, turn and keys stay, and so does home, so depth
layers keep their parallax. Layers in the world don't move. **Pinned layers keep their distance from the frame's
centre**, so a centred title stays centred. One change, one undo step; the view refits if it was fitted.

So Wide 16:9 → Vertical 9:16 shows the middle of the old picture, not its left edge; move the frame (or **Frame these**)
to choose another part. **Fill the frame** and **Align to the frame** use the frame where it is at the playhead.


## Motion blur (shutter)

Two fields on the **composition** (set with `comp.set`, or `comp("main", shutter=180)`; not animatable). On the screen:
pick the scene, click **+ Motion blur**: it is on at 180° (**Amount**), with **Blur steps** under it; **−** turns it off.

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
- `look_world time=3`: the **whole canvas** as the world view draws it, with the frame outlined at that time, the part outside it veiled, its **path** (a dot per frame, a faint outline and a time label at each key, a cut as a dashed line) and a ruler of world px along the top and left. `area` is `all` (every layer and the whole path), `frame`, or `{x, y, w, h}` in world px; `path=false` leaves the path off. The reply gives the frame's corners in world px and the rectangle shown. Use it to find layers beside the frame, to see where the frame goes, and to read world px for `look_at` and Export › Area.
- `look_in_frame time=3`: what is **in** the frame (all of its box in the picture), **partly** in (with the share in %) or **out**, per top-level layer, whether it shows at all (`why_not_showing`: opacity 0, outside its times, a matte), and its box in picture px and in world px. With `from` and `to` (and `step`): per layer the time spans it is in the frame, when it enters and leaves; it looks at the frame's keys and each layer's start and end as well as a regular step. Boxes only: `look_frame` shows the real picture.
- `look_at x y time`: boxes are where the layer shows **in the picture**, through the frame (the reply gives the frame's `x`, `y`, `zoom`, `rotation` as `frame_at`). `space=world` reads x, y as world px instead, with boxes where the world view draws each layer, and says whether the point is inside the frame then.
- `look_path layer=frame` (or any layer): the path it travels, sample by sample: its own x / y and where it shows on
  screen, its keys with their handles, the path's length and its top speed.
- `look_motion`: facts from each layer's own keys, the frame's included; it does not add the frame's motion to other layers.
- `look_rig`, `inspect_rig_motion`: skeletons are drawn where the character shows; the foot-slide check undoes the frame so a
  moving frame is not read as a slide.

## Not yet

Looking through a turned frame straight (the canvas turning with it). Handheld shake or frame noise, a look-at target that follows a layer (it can ride a path, see "A layer riding a path" in `shape-and-path-animation`), depth of field, a frame with perspective in depth (depth is parallax
scaling, not 3D).
