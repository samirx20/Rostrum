# Rostrum2D motion blur, smears and trails (Team Hem, H11)

Three tools for showing speed. All three read the layer's **real motion**: the engine evaluates the whole
composition at other moments (the same evaluation every frame uses), so a layer moved by keys, by its group or
by a rig's bones moves the same way here. They are tools, not looks: plain controls, no presets.

Engine: `engine/render/src/motion/` (shutter.rs, trail.rs, smear.rs; mod.rs holds the field tables and the entry
point). Python field table: `python/rostrum2d/motion/fields.py` (labels, help, when each control shows). The two
tables must match (engine `scene/tests.rs` checks it).

## The document

| Item | Field | Kind | Animatable | Meaning |
|---|---|---|---|---|
| **comp** | `shutter` | number 0..720 ° | no | Shutter angle: how long each frame's shutter is open, in degrees of one frame. 0 = no motion blur (default), 180 = half a frame (the usual film look), 360 = the whole frame. |
| | `shutterSamples` | whole number 2..64 | no | The fewest moments inside the open shutter that are drawn and averaged (fast moves get more: below). Default 8. Shown only when `shutter` > 0. |
| **trail** (effect) | `copies` | whole number 1..32 | no | How many echoes follow the layer. Default 4. |
| | `spacing` | number, frames | yes | Frames between one echo and the next. Default 2. |
| | `fade` | number 0..1 | yes | Each echo's opacity is the one before times this. Default 0.6. |
| **smear** (effect) | `amount` | number 0..10 | yes | How much it stretches per px moved. Default 1. |
| | `max` | number ≥ 1 | yes | The most it ever stretches (times its length). Default 4. |
| | `minSpeed` | number, px per frame | yes | Slower moves don't smear. Default 2. |
| | `stretch` | `behind` / `both` | no | `behind`: the front edge stays put, the stretch trails back along the path (an animator's smear). `both`: stretches about the anchor. |
| | `keepArea` | toggle | no | Thins across the motion as it stretches (keeps its area). Default on. |

## Motion blur

A real camera's shutter stays open for part of each frame; anything moving smears across the picture. The frame
at time *t* is the **average of n pictures** at moments spread evenly over the open shutter, **centred on t**:

    open  = shutter / 360 / fps                       (seconds)
    t_j   = t + open · ((j + ½) / n − ½),  j = 0 … n−1

Centred, so a blurred frame sits where the sharp still at *t* is (a still and the export agree; the blur leads
and trails equally). Each sub-frame is a full evaluation and stage (keys, rigs, trails, smears), drawn and summed
on the GPU (renderer `painter.rs accumulate`). Layers that don't move come out the same in every sub-frame, so they
stay sharp. Whether a layer shows is decided at the frame's own time, as After Effects: a layer showing in a frame
is in every one of its sub-frames (its values before its start or before 0 s hold its first ones), and one not
showing is in none. So the first frame of a piece, or of a layer, is as strong as the next (engine `scene/eval.rs`
`eval`, test `shutter_samples_keep_who_shows`).

**No blur across a jump.** A sub-frame never reads a field past a jump (a key after a `hold` key: a cut of the frame,
a held pose, a step of "on twos"): on the far side of the jump it takes the value on the frame's own side. So a cut
never smears two shots, and a held step doesn't smear into the next. Per field, so other moving layers on that frame
still blur (engine `scene/eval.rs` `shutter_at`, `near_side`; FRAME.md).

**Blur moves things, never changes them (as After Effects).** A field that decides *what* is drawn rather than where it
is placed is read at the frame's own time in every sub-frame: a counter's number (`count`), and which picture shows (a
drawing's frame, paint, grain's frame, a video's frame). So a counting number is one sharp number per frame and a
frame-by-frame drawing never shows two drawings at once; only the layer's movement blurs. The list is data on the field
(engine `scene/fields.rs` `CONTENT`; a new keyable field of that sort is added there).

Exports go through the same `frame` request, so preview ≡ export.

**Steps follow the motion** (engine `motion/steps.rs`, as After Effects' adaptive sample limit). `shutterSamples` is the
fewest. Before a blurred frame is staged, the comp is evaluated (no stage, no paint) at the edges of 4 equal slices of
the open shutter (`streak.rs` `probe_times`; the middle one is the frame's own time, and the streaks below read the same
5 evaluations), each as a sub-frame of the frame (so a cut is never a move); every
layer's box corners (a text's estimated as for smears) are carried to the output through its own x, y, rotation and
scale, its groups' and the frame's (`frame/mod.rs` `map`: pan, zoom, roll, depth). The fastest corner's move across one
slice, × 4, is that layer's px per shutter at its fastest; the frame takes

    n = clamp(ceil(px per shutter / GAP_PX), shutterSamples, MOST)      GAP_PX = 1, MOST = 128

so two neighbouring copies are at most about 1 px apart: a smooth streak, not a ladder of copies. Nothing moving (or
moving under 1 px per step) keeps `shutterSamples`, at no extra cost but the probe (4 evaluations beside the frame's
own, a few ms each on a busy scene). Not measured: what moves inside a layer (a path's shape, letters playing their
keys, a rig's warp, tilt's perspective); raise `shutterSamples` for those.

**A layer that barely moves is drawn once** (engine `motion/hold.rs`). The steps are the frame's, set by its fastest
layer; a layer that hardly moves while the shutter is open (a slow drift, a background, the first instant of an ease)
would give the same picture in every step but for a fraction of a pixel. When each of its box corners (and its
children's and its matte's, measured as above) stays within `HOLD_PX` = 0.25 px of where it is at the frame's own time,
and its markup differs from that time's only in numbers that each stay within 0.25 (path points, letter places,
opacity, a blur's radius), it is drawn as at the frame's time, once, with no streak.
Its streak would have been under half a pixel long; the frame differs from drawing it every step only on hard edges, by
what moving that edge a quarter of a pixel does. A colour written in hex that changes, or a layer that starts or ends
inside the shutter, is drawn every step as before. Export-speed bench (2026-10-29, 20 s at 1080p, blurred blobs under
a fast title): 39 s → 31.5 s; worst frame 29 levels on one title edge, average 0.12 of a level, no visible change.

**One streak per layer** (engine `motion/streak.rs`, `blurred.rs`; 2026-10-29). Each sub-frame's comp is evaluated
(no stage, no layout). A top-level layer that, in every sub-frame, is the same layer but for where it is placed (its x,
y, turn and scale, and the frame's move, zoom and roll on it at its depth; any other field within 0.25; its matte, if
it has one, the same picture moved alike, within 0.25 px; no smear, no turn or scale change under a tilt) is the same picture moved: the page is laid out once, at the frame's own
time, that layer is painted once (with its depth-of-field blur) and drawn as its **streak**: the average of the picture
under each sub-frame's move, one GPU pass of up to 128 reads a pixel (anyrender `draw_cached_streak`), one read per px
of its longest path. Turning and scaling streak per pixel as they should (each read goes through the whole move, not a
slide). Layers in a row that move alike (the same depth under a pan) are one picture and one streak. Streaks that don't read
each other's pictures share one picture, painted together (`blurred.rs` `shares`): where a streak reads is its reach
inside the frame, rounded out to whole device px and pulled back through every one of its moves (each sub-frame's
picture px it averages), held inside the picture; two runs share only when neither reads where the other's picture is.
All of a step's pictures are made in **one paint** of the page, each run's layers drawn into their own picture
(blitz-paint `Run::Keep`, anyrender `begin_kept`), not one paint per picture. What a layer
streaks over is what lies under it, so this is each layer's own motion blur laid over the others, as After Effects
blurs each layer: where two layers that move differently overlap, it differs a little from averaging whole sub-frames.
A layer that only moves but blends (a blend mode, glow, frosted glass) is painted as laid out, moved to each
sub-frame (one per px of its path), over the layers under it and averaged: no layout per step. In an export or a still
(the page at its own size) the pictures reach up to 128 px past each edge of the frame (`blurred.rs` `MARGIN`), so a
layer that runs past the edge streaks what lies there in; a moving layer whose streak reads further past the edge than
that, or whose size isn't known before layout (a text, a path), or any in a zoomed or cropped view, is built like a
blending one, alone; one that covers the whole frame (a backdrop) takes its picture's edge px for the px a move pulls in
past that; a streak that never reaches the frame isn't drawn. The layers are evaluated at 5 times spread over
the open shutter (`streak.rs` `probe_times`, shared with the step count) and the moves at each sub-frame read off them,
straight between the two probes around it; a fade or a colour change within one shutter opening is taken at the frame's time (its
average). A layer still staged per sub-frame gets as many sub-frames as its own corners (and its matte's) travel in px,
at least `shutterSamples`, not the frame's count; only its own pieces are written at each sub-frame (`stage.rs`
`parts_of`). A top-level layer with nothing keyed inside it (its children, effects, masks and stops; no rig, not following
a path) is evaluated at the probes by its own fields only, its insides taken from the frame's own (`eval.rs`
`at_reusing`; not in a comp with trails or smears). A layer's blur, shadow and stroke reach past its boxes is scaled by
how much it is stretched on screen (its scale, its groups', the frame's zoom: `steps.rs` `widest`). A frame's
`timing.evalSplit` says where its evaluation ms went (probes, steps, moves, staged sub-frames, holds); with
`ROSTRUM2D_PROFILE` each motion-blur paint is labelled `mb-picture`, `mb-streaks`, `mb-blend`, `mb-edge`, `mb-staged`.

A layer whose look changes while the shutter is open (a path changing shape, letters playing, a colour, a layer whose
matte changes or moves differently) or that can't be laid over on its own (a blend mode, glow, frosted glass) is staged and painted at every
sub-frame, alone, over the picture of the layers under it, and averaged; the layers above it are drawn once over that.
Only such layers cost a layout per step. When the sub-frames draw different layers (one starts or ends inside the
shutter), every sub-frame is drawn whole, as before. At most `KEPT_BYTES` (serve.rs, 768 MB) of streak pictures are kept
at once; past it the picture so far is kept as one and the next streaks follow it. The frame's depth of field (focus,
blur) is as at the frame's own time in every sub-frame.

**Request override (agents, previews):** `{"frame": {"t": 1.5, "shutter": 180, "shutterSamples": 1}}` overrides
the comp's values for that one frame, and its `shutterSamples` is then the exact count, not adapted (1 sample = no blur:
a fast preview while playing; or a timing test at 8 vs 16). The screen's playback sends 1 while time moves unless
**Motion blur while playing** is on; then it sends nothing and plays the comp's own adaptive steps, exactly as export.

**Cost:** one layout of the page, two paints (the streak pictures, then the frame), and one streak pass per moving
layer (its cost grows with its steps); a layer that blends, or reads too far past the frame's edge, costs a paint per
step; a layer that changes while the shutter is open costs a stage and paint per step.

## Trails

Echo copies of the layer drawn just **behind** it. Copy *i* (1 … copies) is the layer itself as it was at

    t_i = t − i · spacing / fps,   opacity × fade^i

It is taken out of the whole composition evaluated at t_i, so a rig-bound or nested layer's echoes keep their
pose and place. Copies are drawn in their parent just before the layer, oldest (faintest) first. A layer that
wasn't showing at t_i (before its start) has no echo there. Echoes carry the layer's other effects (a smear echo is
smeared as it was then) but not a trail of their own. Their ids are `<id>~trail<i>` (and their children's too).

**Cost:** one composition evaluation per copy (plus one more per copy when the layer smears), and the copies are
drawn like any layer.

## Smear

The layer stretched along the way it is moving, by its speed. The velocity is the layer's own move over the last
frame, in its parent's px (its x, y after rig binds):

    d      = position(t) − position(t − 1/fps)           px this frame; speed = |d|
    length = the layer's box (scaled and turned as it is) measured along d
    k      = clamp(1 + amount · max(0, speed − minSpeed) / length, 1, max)

So with amount 1, a layer that moves its own length in one frame doubles in length. The stretch is k along the
motion and 1/k across it (`keepArea`) or 1, about the anchor, in the parent's space (it is applied after the
layer's own rotation and scale). With `stretch` = `behind` it is also shifted back by (k − 1) × (anchor-to-front
distance), so the leading edge stays where it is.

Notes:
- It reads the layer's **own** motion: a layer that only moves because its group moves doesn't smear; put the smear
  on the group.
- Text has no box before layout, so its length is estimated from its size and letters (0.6 × size per letter on the
  longest line, or its box width); `amount` tunes it.
- **Cost:** one more composition evaluation per frame (shared by every smearing layer).

## Seeing it (agents)

`look_frame` at the fastest moments shows the smear, the echoes and the blur; `look_frame` (`what: "sheet"`) over the move shows how
they grow and settle. A smear frame should read as one stretched shape; motion blur on a fast move should read as one streak (steps adapt
to layer and frame moves; if steps show inside a layer that changes shape fast, raise `shutterSamples`).

## Motion samples (the hand-off to RostrumSound)

`render_export format="motion"` (the Export panel's **Motion samples**) writes where each moving layer is, many times a
second, as one JSON file. RostrumSound's `edit_sounds_from_motion samples=<file>` reads it and suggests a musical answer (a note or hit on a landing, a string or cymbal rise into it) for each
move, a click where something lands, presses, snaps and ticks. Nothing is rendered; it is read from the composition as
it plays (`rostrum2d/motion_samples.py`, through the same geometry as the look tools), so layers timed from markers,
groups and auto layouts are where they show.

```json
{"format": "rostrum.motion-samples/1", "comp": "film", "rate": 60, "duration": 20.0, "width": 1920, "height": 1080,
 "layers": {"card0": {"type": "group", "x": [960.0, …], "y": […], "scale": […], "opacity": […], "w": 820.0, "h": 180.0},
            "camera:frame": {"type": "camera", …}}}
```

- `x`, `y`: the centre of the layer's box in the frame, in pixels; `scale`: its size against its own (parents
  included); `opacity`: with its groups', 0 outside its start / end. One value per sample, sample `i` at `i / rate` s.
  `w`, `h`: the largest box it shows at.
- Layers are placed in the scene **without the frame**; the frame, when it moves, is its own entry `camera:<frame id>`
  (the output's centre point through it, its zoom as `scale`), so a whip of the frame is one moment, not one per layer.
- Off its time a layer holds still (its nearest place), so a cut is never a move. A cut of the frame (a hold key) is one
  step of its entry.
- Default layers: every layer and camera whose own values change while it shows. `layers=[…]` picks them.
- Read-only for Sound: change the picture, export again, run `edit_sounds_from_motion` again; it moves its sounds and
  keeps what a person changed. The sounds land on seconds, not on markers.
