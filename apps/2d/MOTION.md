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
| | `shutterSamples` | whole number 2..64 | no | How many moments inside the open shutter are drawn and averaged. Default 8. Shown only when `shutter` > 0. |
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
stay sharp. A layer that starts or ends inside the open shutter fades in or out across it, as on film.

Exports go through the same `frame` request, so preview ≡ export.

**Request override (agents, previews):** `{"frame": {"t": 1.5, "shutter": 180, "shutterSamples": 1}}` overrides
the comp's values for that one frame (1 sample = no blur: a fast preview; or a timing test at 8 vs 16).

**Cost:** about n times a sharp frame (n stages written and painted). 8 samples is a good start; push to 16–32
only for very fast spins or whips where the steps show.

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

`look_frame` at the fastest moments shows the smear, the echoes and the blur; `look_sheet` over the move shows how
they grow and settle. A smear frame should read as one stretched shape; if the steps of motion blur show, raise
`shutterSamples`.

## Motion samples (the hand-off to RostrumSound)

`render_export format="motion"` (the Export panel's **Motion samples**) writes where each moving layer is, many times a
second, as one JSON file. RostrumSound's `edit_sounds_from_motion samples=<file>` reads it and places a whoosh on each
move, a click where something lands, presses, snaps and ticks. Nothing is rendered; it is read from the composition as
it plays (`rostrum2d/motion_samples.py`, through the same geometry as the look tools), so layers timed from markers,
groups and auto layouts are where they show.

```json
{"format": "rostrum.motion-samples/1", "comp": "film", "rate": 60, "duration": 20.0, "width": 1920, "height": 1080,
 "layers": {"card0": {"type": "group", "x": [960.0, …], "y": […], "scale": […], "opacity": […], "w": 820.0, "h": 180.0},
            "camera:cam_ui": {"type": "camera", …}}}
```

- `x`, `y`: the centre of the layer's box in the frame, in pixels; `scale`: its size against its own (parents
  included); `opacity`: with its groups', 0 outside its start / end. One value per sample, sample `i` at `i / rate` s.
  `w`, `h`: the largest box it shows at.
- Layers are placed in the scene **without the camera**; each camera that moves is its own entry `camera:<id>` (the
  scene's centre point through that camera, its zoom as `scale`), so a camera whip is one whoosh, not one per layer.
- Off its time a layer holds still (its nearest place), so a cut is never a move. Cameras never step.
- Default layers: every layer and camera whose own values change while it shows. `layers=[…]` picks them.
- Read-only for Sound: change the picture, export again, run `edit_sounds_from_motion` again; it moves its sounds and
  keeps what a person changed. The sounds land on seconds, not on markers.
