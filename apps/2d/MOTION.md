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
fewest. Before a blurred frame is staged, the comp is evaluated (no stage, no paint) at the edges of k equal slices of
the open shutter (k = `shutterSamples`, 2..16), each as a sub-frame of the frame (so a cut is never a move); every
layer's box corners (a text's estimated as for smears) are carried to the output through its own x, y, rotation and
scale, its groups' and the frame's (`frame/mod.rs` `map`: pan, zoom, roll, depth). The fastest corner's move across one
slice, × k, is that layer's px per shutter at its fastest; the frame takes

    n = clamp(ceil(px per shutter / GAP_PX), shutterSamples, MOST)      GAP_PX = 1, MOST = 128

so two neighbouring copies are at most about 1 px apart: a smooth streak, not a ladder of copies. Nothing moving (or
moving under 1 px per step) keeps `shutterSamples`, at no extra cost but the probe (k + 1 evaluations, well under a
millisecond each on a typical scene). Not measured: what moves inside a layer (a path's shape, letters playing their
keys, a rig's warp, tilt's perspective); raise `shutterSamples` for those.

**A layer that barely moves is drawn once** (engine `motion/hold.rs`). The steps are the frame's, set by its fastest
layer; a layer that hardly moves while the shutter is open (a slow drift, a background, the first instant of an ease)
would give the same picture in every step but for a fraction of a pixel. When each of its box corners (and its
children's and its matte's, measured as above) stays within `HOLD_PX` = 0.25 px of where it is at the frame's own time,
and its markup differs from that time's only in numbers that each stay within 0.25 (path points, letter places,
opacity, a blur's radius), it is written as at the frame's time in every step, so it is painted once (`still_runs.rs`).
Its streak would have been under half a pixel long; the frame differs from drawing it every step only on hard edges, by
what moving that edge a quarter of a pixel does. A colour written in hex that changes, or a layer that starts or ends
inside the shutter, is drawn every step as before. Export-speed bench (2026-10-29, 20 s at 1080p, blurred blobs under
a fast title): 39 s → 31.5 s; worst frame 29 levels on one title edge, average 0.12 of a level, no visible change.

**A fast frame move is cheap** (engine `scene_serve.rs` `stage_at`, `still_runs.rs`). When the frame (camera) moves
faster than the layers do on their own, the steps are measured a second time with the frame held where it is at the
frame's time (`steps.rs` `own_steps`): that many steps are what the layers' own moves need. The n sub-frames are then
split into that many equal groups. In a group the layers are as at its middle sub-frame and only the frame moves, so
each top-level layer that blends normally is painted once per group and its picture is moved for the other
sub-frames (staging, layout and painting skipped). A whip pan needing 128 steps whose layers need 16 paints 16 times,
not 128. The picture is the same up to resampling (a picture moved by a fraction of a px is sampled smoothly) and the
few px a move uncovers at the frame's edge, which take the picture's edge px. Layers with a blend mode, glow or frosted
glass are still drawn each sub-frame. A request's own `shutterSamples` never groups.

**Request override (agents, previews):** `{"frame": {"t": 1.5, "shutter": 180, "shutterSamples": 1}}` overrides
the comp's values for that one frame, and its `shutterSamples` is then the exact count, not adapted (1 sample = no blur:
a fast preview while playing; or a timing test at 8 vs 16). The screen's playback sends 1 while time moves unless
**Motion blur while playing** is on; then it sends nothing and plays the comp's own adaptive steps, exactly as export.

**Cost:** about n times a sharp frame (n stages written and painted; layers that keep still are painted once:
`still_runs.rs`). Only the fast frames take more steps, so an export with one whip pan costs a little more in total.

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
