# Drawing and frame-by-frame

How to draw in Rostrum2D with the shared painting kit: real brush strokes in the document, the same ones a person draws
with a pen on the Draw page. This guide is about the tools; what you draw is yours.

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
- New drawing: `frame.add at=N` (blank) or `frame.add at=N copy=<frame id>` (start from a copy and change it).
- Redraw: `paint.clear` on the paint layer, then new strokes; or `stroke.remove` single strokes.

## The brush (`inspect_operations name: stroke.add` lists every setting)

| Setting | Use |
|---|---|
| `brush` | `round` soft dab · `bristle` dry brush with streaks · `chalk` broken by paper grain · `flat` wide flat brush · `block` square-ended block-in · `line` crisp thin line |
| `size`, `opacity`, `hardness` | width in px; 0..1; soft to hard edge |
| `mode` | `normal`, `multiply` (glaze), `erase`, `screen` / `add` (light that builds up) |
| `smudge` + `wet` (+ `pickup`) | the brush drags the paint under it (and from the layers below) |
| `grain`, `color_jitter`, `hue_jitter`, `jitter`, `spacing` | paper tooth, colour drift along the stroke, scatter, dab spacing |
| `follow` / `angle` | the tip turns with the stroke, or keeps a fixed angle |

## Seeing and checking

- `look_drawing layer=… frame=N`: the drawing shown at frame N, in canvas px with a labelled grid (`grid`, `zoom`
  `[x0, y0, x1, y1]` for detail, `paint` for one paint layer, `onion=true` for the 2 drawings before (red) and after
  (green)).
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
