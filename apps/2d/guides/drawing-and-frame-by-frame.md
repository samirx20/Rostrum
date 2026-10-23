# Drawing and frame-by-frame

How to draw in Rostrum2D with the shared painting kit: real brush strokes in the document, the same ones a person draws
with a pen when the Brush is on. This guide is about the tools; what you draw is yours.

## The parts

```
drawing layer (w × h canvas, placed like any layer) ─ frames ─ frame (at = frame number) ─ paints ─ paint ─ strokes
                                                                                          ─ paintmasks
```

- A **drawing layer** has a canvas `w × h` px. Untransformed and placed at its default spot, canvas px = composition px.
- A **frame** is one drawing. It shows from frame `at` until the next drawing (it is **held**); nothing shows before the
  first. Drawings on twos = a drawing every 2 frames. `frame.hold frames=3` makes one last 3 frames and moves the later
  ones.
- A **paint** layer (blend `normal`, `multiply`, `screen`, `add`; opacity; visible; locked) holds **strokes** in painting
  order. Several paint layers on one drawing: e.g. a base and a light layer in `add`.
- A **stroke** is a path `[[x, y, pressure], …]` in canvas px plus a brush. Pressure 0..1 thins and fades the mark
  (`size_pressure`, `opacity_pressure`). The seed is fixed when it is made, so it repaints identically.
- A **paint mask** is a polygon; a stroke with `mask` set paints only inside it (`invert` = outside).

## Making strokes

- One `edit_document` call list = **one undo step**: put a whole pass (say, the 30 strokes of one drawing's base) in one
  call list. `undo` takes the whole pass back.
- Or `run_script`: `d = drawing("fx", w=800, h=1000)`, `f = d.frame(0)`, `ink = f.paint("ink")`,
  `ink.stroke([(x, y, p), …], color="#rrggbb", size=24, brush="bristle")`. Ids you write (`"ink"`) stay put; a re-run
  merges stroke by stroke, so a drawing a person redrew is kept (the reply lists what was held).
- New drawing: `frame.add at=N` (blank) or `frame.add at=N copy=<frame id>` (start from a copy and change it). `at` left out
  puts it after the last drawing, held by the layer's `newHold` (1–4, default 2: the screen's "New ones hold"). It turns
  `eachFrame` (the screen's "Draw each frame") on.
- Redraw: `paint.clear` on the paint layer, then new strokes; or `stroke.remove` single strokes.
- Fill a closed area: `paint.fill {target: <layer>, at: [[x, y]], color, opacity, gap: small|medium|large, layer}`
  (composition px; `space: "canvas"` for canvas px). The edges come from every visible paint layer of that drawing,
  so fill a colour layer under a line layer; `gap` closes line ends that don't quite meet. The fill is a `fill` item
  (its outline, ring 0 outside, 1.. holes) in the paint layer's `strokes`: sharp, one undo step, removed with
  `stroke.remove`. A point on a line or in an open area is refused with the reason; nothing changes.
- Paint layers: `paint.add {name}` on a drawing (frame) adds one on top (the screen's **Paint layers +**);
  `stroke.add`/`paint.stroke` with `layer: "new"` starts one with the stroke; `paint.set` (name, mode, opacity,
  visible, locked), `paint.move {index}` (0 = bottom), `paint.remove`.

## The brush (`inspect_operations name: stroke.add` lists every setting)

| Setting | Use |
|---|---|
| `brush` | `round` soft dab · `bristle` dry brush with streaks · `chalk` broken by paper grain · `flat` wide flat brush · `block` square-ended block-in · `line` crisp thin line |
| `size`, `opacity`, `hardness` | width in px; 0..1; soft to hard edge |
| `mode` | `normal`, `multiply` (glaze), `erase`, `screen` / `add` (light that builds up), `overlay`, `soft_light`, `color`. A paint layer's own `mode` is `normal`, `multiply`, `screen` or `add` |
| `smudge` + `wet` (+ `pickup`) | the brush drags the paint under it (and from the layers below) |
| `steady` | Steadiness: the line trails the pen and smooths a shaky hand (0 = raw) |
| `size_pressure`, `opacity_pressure`, `tilt_angle`, `tilt_size` | what a pen's pressure and lean change (a stroke's points may carry tilt: `[x, y, pressure, tiltX, tiltY]`) |
| `taper_start`, `taper_end` | the stroke starts / ends thin over this many tip sizes |
| `texture` | tip picture: `none`, `sponge`, `speckle`, `streaks`, `ragged`, `charcoal`, or a picture in the project's library; it turns with the tip |
| `paper`, `paper_scale`, `grain` | the paper's tooth (`tooth`, `canvas`, `cold press`, `laid`, `rough`, or the project's own) and how much it breaks up the paint; it stays put on the canvas |
| `color_jitter`, `hue_jitter`, `jitter`, `size_jitter`, `angle_jitter`, `spacing`, `even` | colour drift along the stroke, scatter, random size and turn per dab, dab spacing, softer tips closer together |
| `follow` / `angle` | the tip turns with the stroke, or keeps a fixed angle |

The screen's 19 shipped brushes (Sketch, Ink, Paint, Light, Texture) are only ready-made sets of these settings; a stroke
records what it was drawn with, so an agent sets the same ones.

**My brushes** are the project's saved brushes, shared with the person (the brush panel lists them last).
`run_brush {action: "list"}` gives each one's `id`, `name` and `stroke`: pass `stroke` to `paint.stroke` with your points
and colour to paint with it. `run_brush {action: "save", name, settings}` keeps a set of these settings as a brush
(colour and seed are never kept; a loaded tip or paper stays named by its item id). `rename` (id, name) and `delete` (id)
do what the brush's right-click menu does. A brush is kept by its settings: saving the same settings again renames it.

## Seeing and checking

- `look_drawing layer=… frame=N`: the drawing shown at frame N, in canvas px with a labelled grid (`grid`, `zoom`
  `[x0, y0, x1, y1]` for detail, `paint` for one paint layer, `onion=true` for 2 drawings before (red) and after
  (green), or `onion={before, after}` with 0 – 5 each way, as the screen's onion skin).
- `look_drawing_change`: before / after of the last change to that drawing, with the changed box.
- `inspect_drawing_at x y`: the colour there, each paint layer's colour, the top stroke and who drew it.
- `inspect_stroke_landed stroke=…`: did the paint land on the path (mean / worst px off); give `path` to compare with
  where you meant it to go.
- `look_frame`, `look_sheet`, `render_video`: the whole composition, drawn by the engine exactly as it exports.

## Stepped timing

- **Drawings:** each drawing is held until the next, so "on twos" is drawings at frames 0, 2, 4 …; "on threes" is 0, 3, 6.
  `frame.hold frames=N` changes how long one shows and shifts the later ones. The last drawing is held to the layer's end
  (`end`); add a drawing after it to end a hold.
- **Other layers:** the `hold` ease makes any field jump at the next key instead of travelling: `layer.key("x", {0: 100, 0.2: 300}, ease="hold")`
  steps a layer; keys every 2 frames with `hold` give a stepped move. `linear` between keys is smooth motion.
- A drawing layer's own keys (opacity, position, scale) work like any layer's.

## Frame-by-frame working method

1. Block the motion first: a few key drawings (the extremes), checked with `look_sheet`.
2. Fill the in-betweens with `onion=true`, so each drawing sits between its neighbours.
3. Check the loop: the last drawing must lead into the first. `render_video` and watch it.

## Not yet

Auto in-betweening of drawings, and animating a single stroke's own path with keys.
