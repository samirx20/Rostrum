# Drawing and frame-by-frame

How to draw in Rostrum2D with the shared painting kit: real brush strokes in the document, the same ones a person draws
with a pen when the Brush is on. This guide is about the tools; what you draw is yours.

## The parts

```
drawing layer (w × h canvas, placed like any layer) ─ frames ─ frame (at = frame number) ─ paints ─ paint ─ strokes
                                                                                          ─ paintmasks
```

- A **drawing layer** has a canvas `w × h` px. Made in a script without `x`, `y`, its canvas's top-left sits on the
  comp's (or its group's) top-left, whatever its size: canvas px = composition px, so `drawing("cliff", w=1100, h=620)`
  painted at (1500, 900) shows at (1500, 900). Give `x`, `y` (where its anchor, default the centre, goes) to place it
  elsewhere; then canvas px start at its top-left. The `paint.stroke` operation takes comp px by default either way.
  The canvas **grows with the strokes, in any direction**: `paint.stroke` past an edge makes it bigger (in 256 px
  steps) in the same undo step, and so does a script's stroke or fill when the script runs (the `w`, `h` you give
  `drawing(...)` are a starting size, never a crop) (an erasing stroke, `mode: "erase"`, never grows it: past the edge there is nothing to
  take away). Growing left or up moves every stroke, fill and paint mask of every drawing by the same
  amount in canvas px and moves the anchor with them, so nothing moves on screen (re-read canvas px after a stroke that
  grew it: `look_drawing` (`what: "at"`), `look_drawing`). Its picture holds only the painted rectangle, so empty canvas costs
  nothing.
- **Turning or scaling a drawing round a point** (a beam round its lantern, an arm round its shoulder): never work out
  `anchorX` from the grown canvas. In a script write `beam.pivot(1842, 640)`: the anchor goes on that point in comp px
  (or the group's box) and `x`, `y` move with it, so nothing moves on screen; before or after the strokes, the same
  result (growth keeps the anchor on its spot). With operations: `layer.anchor` with `point: [1842, 640]`. It keeps the
  picture where it shows at `at` (default 0 s): call it before keying `x`, `y` or the anchor.
- At most **8192 px a side**. A stroke that would grow a drawing past that goes into a **new drawing layer** just above
  it (same parent, depth, pin, position, scale, turn and keys; named "<name> 2", "<name> 3" …), in the same undo step;
  the screen says "'sky' is at its largest; this stroke started 'sky 2'". Never a lost or cropped stroke.
- A **frame** is one drawing. It shows from frame `at` until the next drawing (it is **held**); nothing shows before the
  first. Its id (`frame_6`) is a counted name, not a frame number: `look_drawing` says "char at frame 0 shows its
  drawing 1 of 12, which starts at frame 0 (id frame_6 …)". `at` counts the layer's frames as written: inside a group
  timed from a marker (`marker=`), frame 0 is the marker's moment, so moving the marker moves every drawing with it. Drawings on twos = a drawing every 2 frames. `frame.hold frames=3` makes one last 3 frames and moves the later
  ones.
- A **paint** layer (blend `normal`, `multiply`, `screen`, `add`; opacity; visible; locked) holds **strokes** in painting
  order. Several paint layers on one layer: e.g. a base and a light layer in `add`. Paint layers stack in the order they
  are made: a later layer shows in front of every earlier one, so a patch on it that lies partly on an earlier shape (a
  window over an awning) shows in front of that shape; the look names it (`painted_over`). Paint what is behind first. In a layer that draws each frame
  the paint layers belong to the layer and are shared by all its drawings; each drawing keeps its own strokes in each.
- A **stroke** is a path `[[x, y, pressure], …]` in canvas px plus a brush. Pressure 0..1 thins and fades the mark
  (`size_pressure`, `opacity_pressure`). The seed is fixed when it is made, so it repaints identically.
- A **paint mask** is a polygon; a stroke with `mask` set paints only inside it (`invert` = outside).

## Making strokes

**The script calls for drawings, on one card:**

| Call | Gives |
|---|---|
| `d = drawing(id, w=, h=, eachFrame=, loop=)` | A drawing layer; no `x`, `y`: canvas px = comp px |
| `f = d.frame(at)` | Its drawing at frame `at`; asking again for the same `at` gives the same drawing |
| `ink = f.paint(id)` / `f.paint()` | A paint layer on it (each call a new one; keep the handle to paint more on it) |
| `ink.stroke(points, size=, color=, brush=, hardness=, opacity=, mode=, mask=)` | A brush stroke, points in canvas px `(x, y[, pressure])` |
| `ink.fill(points, color=, mask=)` | A sharp filled polygon (fades in, not drawn, under `drawnSoFar`) |
| `m = f.paintmask(points, invert=, feather=)` | A paint mask; `stroke(..., mask=m)` keeps the stroke inside it (`m` or its id) |
| `d.pivot(x, y)` | Its turning point on a comp point, nothing moves |
| `d.key("drawnSoFar", {...})`, `d.key("scaleX", {...})` | Paint it on over time; squash or mirror it |

- One `edit_document` call list = **one undo step**: put a whole pass (say, the 30 strokes of one drawing's base) in one
  call list. `undo` takes the whole pass back.
- Or `run_script`: `d = drawing("fx", w=800, h=1000)`, `f = d.frame(0)`, `ink = f.paint("fx_ink")`,
  `ink.stroke([(x, y, p), …], color="#rrggbb", size=24, brush="bristle")`. Ids you write (`"fx_ink"`) stay put; a re-run
  merges stroke by stroke, so a drawing a person redrew is kept (the reply lists what was held).
- **A paint layer's id is one in the whole document**, like every id: two drawing layers can't both have a paint layer
  `"ink"`. Name each after its drawing (`sky.frame(0).paint("sky_ink")`, `cliff.frame(0).paint("cliff_ink")`), or leave
  the id out (`f.paint()`: one is counted for you).
- **Several drawings from a script:** every id is one in the whole document, but the drawings share their paint layers.
  So in each drawing write `f.paint()` (no id: it joins the layer made in the first drawing, at the same place), or
  `f.paint(f"ink{i}", layer="ink")` to name it (the same `layer="ink"` in every drawing). `f.paint("ink")` in a second
  drawing is refused (id used twice). The drawings also need `eachFrame=True` on the drawing layer, or only drawing 1 shows
  (the reply warns when a set of drawings shows only the first). A re-run under the same script `name` replaces them; under
  a new name it adds a second set at the same frames, which is refused.

  ```python
  c = comp("title", width=1280, height=720, fps=24, duration=2, background="#14121f")
  blob = drawing("blob", w=1280, h=720, x=640, y=360, eachFrame=True)
  for i in range(8):                                    # N drawings in a loop, one every 6 frames
      f = blob.frame(i * 6)
      ink = f.paint(f"ink{i}", layer="ink")             # the same layer="ink" in every drawing
      r = 60 + 40 * i
      ink.stroke([(640 - r, 360), (640, 360 - r, 0.8), (640 + r, 360), (640, 360 + r, 0.8), (640 - r, 360)],
                 color="#ffb040", size=30, brush="round")
  ```
  `look_frame` (`what: "sheet"`) then shows the drawing changing from frame to frame; `look_drawing layer=blob frame=N` shows one drawing.
- **A fill in a script:** `ink.fill([(x, y), …], color="#2a2340", opacity=1)` lays a filled polygon (the same item
  `paint.fill` makes from a click, `fill.add` in an edit): a silhouette or a ridge in one call. Add a third number
  per point for holes (`[x, y, ring]`, ring 0 the outside).
  A refusal "drawing … must have the same paint layers" means a drawing's paint lacks that shared `layer="…"`.
- **Paint it on over time:** key the drawing layer's `drawnSoFar` 0 → 1 (`d.key("drawnSoFar", {0.5: 0, 2.5: 1})`): its
  strokes appear in the order they were painted, each along its own path with a round tip (drawing.md, part 10). A fill
  (`ink.fill`) is not drawn along a path: its whole area fades in over its share (a ghost of the full shape mid-way), so
  stroke its outline before the fill when it should look drawn. Paint on an element takes it too.
- New drawing: `frame.add at=N` (blank) or `frame.add at=N copy=<frame id>` (start from a copy and change it). `at` left out
  puts it after the last drawing, held by the layer's `newHold` (1–4, default 2: the screen's "New ones hold"). It turns
  `eachFrame` (the screen's "Draw each frame") on. `set <element> eachFrame true` works on an element that has no paint yet
  too: its first stroke then makes drawing 1 at that frame. A blank drawing starts with the same paint layers, empty; a copy
  puts the current drawing's strokes into those same paint layers.
- Redraw: `paint.clear` on the paint layer, then new strokes; or `stroke.remove` single strokes. Both stay per drawing:
  they touch only that drawing's strokes.
- Fill a closed area: `paint.fill {target: <layer>, at: [[x, y]], color, opacity, gap: small|medium|large, layer}`
  (composition px; `space: "canvas"` for canvas px). The edges come from every visible paint layer of that drawing,
  so fill a colour layer under a line layer; pass `edges: "layer"` to use only the paint layer's own lines. A locked
  paint layer refuses paint and fill. `gap` closes line ends that don't quite meet. The fill is a `fill` item
  (its outline, ring 0 outside, 1.. holes) in the paint layer's `strokes`: sharp, one undo step, removed with
  `stroke.remove`. A point on a line or in an open area is refused with the reason; nothing changes. An area that
  runs out to the drawing's edge is never filled: "This area isn't closed: it runs out to the drawing's edge. Close the
  gap, or raise Close gaps." A point outside the canvas: "That click is outside the drawing."
- Paint layers: `paint.add {name}` adds one on top (the screen's **Paint layers +**); on a layer that draws each frame
  it adds it to every drawing at once (empty in the others). `stroke.add`/`paint.stroke` with `layer: "new"` starts one
  with the stroke; `paint.set` (name, mode, opacity, visible, locked, ground), `paint.move {index}` (0 = bottom),
  `paint.duplicate` (a copy just above with every stroke and fill, "<name> copy", the same pixels; the screen's
  right-click **Duplicate**), `paint.remove`, `paint.unlock`. On one drawing's paint layer these act on all its copies
  in every drawing; each copy of a duplicate holds that drawing's own strokes. One edit is one undo step.
- Every paint layer of a layer that draws each frame carries a shared key, the field `layer` on the paint item, the same
  in every drawing. `paint.stroke` and `paint.fill` take `layer` = a paint layer's id or that key, so one key paints
  "Colour" in whichever drawing you aim at. `background.move` refuses a whole paint layer of a layer with several
  drawings; move its strokes instead.

## The brush (`inspect_operations name: stroke.add` lists every setting)

| Setting | Use |
|---|---|
| `brush` | `round` soft dab · `bristle` dry brush with streaks · `chalk` broken by paper grain · `flat` wide flat brush · `block` square-ended block-in · `line` crisp thin line. A `bristle` or `flat` stroke's start and end fray over about one brush size (a stroke shorter than two sizes frays less) |
| `size`, `opacity`, `hardness` | width in px; 0..1; soft to hard edge |
| `mode` | `normal`, `multiply` (glaze), `erase`, `screen` / `add` (light that builds up), `overlay`, `soft_light`, `color`. A paint layer's own `mode` is `normal`, `multiply`, `screen` or `add` |
| `smudge` + `wet` (+ `pickup`) | the brush drags the paint under it (and from the layers below). `smudge` is on / off; `wet` 1 only drags (a blender), lower also lays that share of the brush's colour; a soft `round` tip blends, a `bristle` tip streaks |
| `steady` | Steadiness: the line trails the pen and smooths a shaky hand (0 = raw) |
| `size_pressure`, `opacity_pressure`, `tilt_angle`, `tilt_size` | what a pen's pressure and lean change (a stroke's points may carry tilt: `[x, y, pressure, tiltX, tiltY]`) |
| `taper_start`, `taper_end` | the stroke starts / ends thin over this many tip sizes |
| `wobble`, `swell`, `pool` | a hand's line from plain x, y points: the path drifts side to side (up to `wobble` × size, smoothly), the width breathes along it (thinning by up to `swell`), and ink gathers where the brush lands and lifts and, less, where it turns a corner (`pool`, 0..2: the ends wider and denser over about half a size). Each 0 = off |
| `load`, `dry` | `bristle` and `flat` tips only. `load` 0..1: how full the brush is: the gaps between the hairs fill, so the line's body is solid ink and only its edges stay ragged (0 = the dry, streaky brush). `dry` 0..1: the brush runs out along the stroke, sooner on long straight runs than where it turns: the outer hairs drop out first, in clumps, so the line thins and its edges break into dry-brush streaks while the middle stays solid longest, and the paper's tooth shows. Every stroke starts full |
| `edge_darken`, `granulation`, `pooling` | how a wash dries, in deeper colour than the stroke (in `normal` mode the colour glazed over itself, as a puddle of the same paint dries darker; in `multiply` another glaze; in `screen` / `add` more light): a dried edge (a thin hard line at the edge and a darker band about a fifth of the size wide inside it, strong in places, faint in others), pigment settled and clumped in the paper's valleys (the `paper` and `paper_scale` pick the tooth), and soft puddles of deeper colour inside the stroke from about two sizes across down to a quarter (`pooling`), so a flat wash is never one even colour. Laid once the stroke is done |
| `bloom` | a backrun: the wet paint runs out past the stroke's edge to a wandering, cauliflower-shaped front (lobes at three sizes, soft but defined), paler inside, with pigment dried darker along parts of the front; up to about 0.6 of the size out at 1.0. Laid once the stroke is done |
| `texture` | tip picture: `none`, `sponge`, `speckle`, `streaks`, `ragged`, `charcoal`, or a picture in the project's library; it turns with the tip |
| `paper`, `paper_scale`, `grain` | the paper's tooth (`tooth`, `canvas`, `cold press`, `laid`, `rough`, or the project's own) and how much it breaks up the paint; it stays put on the canvas |
| `color_jitter`, `hue_jitter`, `jitter`, `size_jitter`, `angle_jitter`, `spacing`, `even` | colour drift along the stroke, scatter, random size and turn per dab, dab spacing, softer tips closer together |
| `follow` / `angle` | the tip turns with the stroke, or keeps a fixed angle |

A paint layer's `ground` (a colour; `paint.add {ground}` / `paint.set {ground}`, or `frame.paint("wash", ground="#2c3552")` in a script) fills that
layer with the colour before its first stroke: a toned paper the strokes go on. See painted-backgrounds.md › Washes,
glazes and an inked line for how these work together.

### Brush settings by technique

What each kind of mark needs from the settings above. These are how the marks are made, not looks to copy: colours,
sizes and where they go are yours.

| Technique | The settings that make it |
|---|---|
| Flat wash (one even colour over an area) | `paint.wash` (below), or by hand: a `round` tip, `hardness` 0.3–0.6, rows no further apart than about `0.1 + 0.6 × hardness` sizes (a stroke is as strong as its strongest dab, so rows further apart leave paler lines), strokes running a size past the area's sides. `flat` / `bristle` tips streak along the rows instead (a dragged, dry look) |
| Graded wash (dark to light, or one colour into another) | `paint.wash` with `to` (the far colour) and `bands` (more = smoother); by hand, rows top to bottom, each a step towards the far colour, or one colour wash then a second `multiply` glaze over part of it under a feathered paint mask |
| Wet-in-wet (colours melting into each other) | low `hardness` (0–0.2) so edges are soft; overlapping strokes of the two colours; then `smudge` on with `wet` 1 on a soft `round` tip along the join to blend (it drags paint, so work over an opaque base or a `ground`) |
| Wet-on-dry (crisp, layered passes) | higher `hardness` (0.5+), `edge_darken` 0.3–0.7 so each pass keeps a dried rim; `mode: "multiply"` for each glaze over the last |
| Dry brush (broken, scratchy paint) | `bristle` or `chalk` tip, `grain` 0.5–1 with a `paper`, little paint: `opacity` 0.5–0.8, fast strokes (few points); `texture` `streaks` or `ragged` for more break-up; on a `bristle` / `flat` tip, `dry` makes it run out along the stroke |
| A watercolour wash (a film of pigment, not brush marks) | a soft `round` tip (`paint.wash` uses one), not `bristle` (its hairs leave parallel streaks: that is a dry brush), `opacity` under 1 so the paper and the layers below show through, `pooling` 0.6–1, `edge_darken` 0.6–1, `granulation` 0.5–0.8 and `grain` 0.2–0.4 (`paint.wash`'s defaults sit here; lower values fade away in a 1920×1080 frame seen small and the wash reads as a flat fill); a crisp, wandering edge from a paint mask (`paint.wash` `bleed` with a small `edge`) rather than a soft one, because a dried wash's edge is hard. Overlapping passes each keep their own dried edge |
| Gouache / opaque paint | `opacity` 1 in `normal`, `pooling` low (0.1–0.3), `edge_darken` low, `hardness` 0.5+; a `flat` tip with `load` 1 for flat, matte block-in with slightly ragged edges |
| Granulating wash (speckled pigment) | `granulation` 0.3–0.8 with `paper` and `paper_scale` choosing the speckle; reads most on flat areas |
| Backrun / bloom (water running into a drying wash) | `bloom` 0.3–1 on the wash's stroke; it reads best on mid and light washes and on a lighter ground |
| Glow / bloom (a lamp, a lantern) | `round`, `hardness` 0, a wide `size`, low `opacity` (0.15–0.4), `mode: "add"` or `"screen"` on its own paint layer, laid last: a small bright core stroke and a wider, fainter one round it. Several lights: vary each one's size, opacity and colour a little (`size_jitter`, `color_jitter` or your own numbers per light) and their spacing, or a row of them reads as stamped copies. A layer-level `glow` / `blur` effect does the same after the fact |
| Inked line | see painted-backgrounds.md › Washes, glazes and an inked line (`wobble`, `swell`, `taper_*`, `pool`, `load`, `dry`) |

### A wash to the edges: `paint.wash`

`paint.wash {target: <paint layer>, color, …}` (script: `p.wash(color=…, …)` on a paint layer `frame.paint()` gave)
lays a wash with the brush going back and forth past every side of its region, so no strip is left bare where a
stroke stopped short or a ragged brush end fell inside the area. It makes ordinary strokes plus one paint mask
(`<id>_edge`), one undo step; `drawnSoFar` paints it on pass by pass.

- Region: the whole canvas (default), `box: [x0, y0, x1, y1]`, or `outline: [[x, y], …]` (a polygon), canvas px.
- `edge`: px the edge is blurred (the mask's feather); 0 = as crisp as the brush. A side on the canvas's edge stays solid there.
- `bleed`: the edge runs out unevenly past the region by up to this many px (paint creeping into damp paper), wandering in long swells and small ripples. Left out on a `box` or `outline`: a fifth of the size, at most 30 px; `bleed: 0` keeps the region's own straight edge.
- `to` + `bands`: a graded wash from `color` (top, or left with `direction: "down"`) to `to`.
- `overlap`: rows this many sizes apart; left out, as far apart as the `hardness` allows with no paler seams.
- `size` defaults to a fifth of the region; every brush setting applies (`brush`, `opacity`, `granulation`, `edge_darken`, `pooling`, `bloom`, `paper`, `wobble`, `mode` …).
- Left out, a wash dries like watercolour, strongly enough to still read in a 1920×1080 frame seen small: `edge_darken` 0.85, `granulation` 0.7, `pooling` 0.9, `grain` 0.3 (the paper's tooth showing through in light specks). Give any of them (0 turns it off) to change it. Weaker drying (around 0.4 / 0.3 / 0.5 and no grain) averages away at frame size and the wash reads as a flat fill; `look_frame` names such an area (below).
- The passes run past the region, but a masked stroke never grows the drawing past its mask, so a whole-canvas wash keeps the canvas size.
- `look_frame` names a wash that is one flat value at frame size (a masked stroke, 1 % of the frame or more): its lightness spread, how much darker its edge is and its grain, in %. Under 3 % spread is flat; at the defaults a wash measures 4–6 % with a rim 3–7 % darker. Very dark washes measure lower: give them more `pooling` or a lighter `to`.
- Where two washes meet edge to edge, a light seam shows (both edges are soft there): overlap them with `bleed`, or keep the seam on purpose.

The screen's 19 shipped brushes (Sketch, Ink, Paint, Light, Texture) are only ready-made sets of these settings; a stroke
records what it was drawn with, so an agent sets the same ones.

**My brushes** are saved brushes, shared with the person (the brush panel lists them last). Each is kept in the
project, in the person's own library (there in every project), or in both; listed once either way.
`run_brush {action: "list"}` gives each one's `id`, `name`, `where` (`project`, `library`) and `stroke`. To paint with
one, `run_brush {action: "use", id}` (it copies a loaded tip or paper from the library into the project if it must),
then pass `stroke` to `paint.stroke` with your points and colour. `run_brush {action: "save", name, settings, where}`
keeps a set of these settings as a new brush (default: both places; colour and seed are never kept; a loaded tip or
paper stays named by its item id, and keeping the brush in the library copies that picture there too). `duplicate`
(id), `rename` (id, name), `delete` (id, everywhere), `keep` / `drop` (id, place) do what the brush's right-click menu
does. Every saved brush is its own brush, even with the same settings as another.

## Seeing and checking

- `look_drawing layer=… frame=N`: the drawing shown at frame N, in canvas px with a labelled grid (`grid`, `zoom`
  `[x0, y0, x1, y1]` for detail, `paint` for one paint layer, `onion=true` for 2 drawings before (red) and after
  (green), or `onion={before, after}` with 0 – 5 each way, as the screen's onion skin).
- `look_drawing layer=… crop=[x, y]` (and `look_painting painting=… crop=[x, y]`): the part around that canvas px at
  100 %, one canvas px to one picture px on flat grey (`width`, default 480). Judge paper grain, chalk and edges here:
  a small or zoomed picture smooths them away or enlarges them.
- `look_drawing` (`what: "change"`): before / after of the last change to that drawing, with the changed box.
- `look_drawing (what "at") x y`: the colour there, each paint layer's colour, the top stroke and who drew it.
- `look_drawing (what "landed") stroke=…`: did the paint land on the path (mean / worst px off); give `path` to compare with
  where you meant it to go.
- `look_frame`, `look_frame` (`what: "sheet"`): the whole composition as the canvas shows it (the export's picture
  without its motion blur; `quality: "final"` adds it); `render_export` (`what: "video"`): the film itself.
- `look_drawing (what "coverage") layer time=…`: how much is painted at that time (as far as `drawnSoFar` has got), per paint
  layer and together (painted = at least 60 % opaque, thin = 15–60 %, bare = less), and each bare area named with its box
  ("bare paper: a 1920×104 px strip along the bottom edge, the full width, canvas x 0–1920, y 976–1080 (composition x 0–1920,
  y 976–1080)"); the picture tints bare paper magenta. A drawing placed straight in the composition is measured over the
  part the composition shows, so paint past the frame doesn't count.

## Painting on a shape, text or other element

`paint.stroke` / `paint.fill` on a shape, text, image or path (not only a drawing layer) paints on that element's own
canvas. Two spaces say where the points are:

- `space: "comp"` (the default): points are composition px, where you see the spot in the picture. The server finds where
  the engine draws the element and turns them into its canvas px. An element that is moved, scaled, turned, inside a
  group or under the frame's camera is still hit where you pointed.
- `space: "canvas"`: points are the element's **own box px**: (0, 0) is the top-left of its `w × h` box, so a 300 × 380
  card takes 0..300 across and 0..380 down, whatever it is doing in the scene.
- `frame` does two jobs: it picks **which drawing** (when the element draws each frame) and it is **the time** the comp
  points are placed at. An element faded in from opacity 0, off its time range or hidden has no place at that frame: the
  refusal names the first frame where it shows ("paint at a frame where the layer shows: pass frame=60"). Pass that
  frame, or use `space: "canvas"`, which doesn't depend on where the element is.

In a script, `painting(...)` and `drawing(...)` take points in their own px; to paint on an element write
`edit_document` with `paint.stroke` (target the element id, points, `frame`, optional `space`).

## Cycles: a run of drawings that repeats

Draw a cycle once (a walk is often 8 or 12 drawings) and let the layer repeat it; never copy drawings for each repeat.

| Setting | What it does |
|---|---|
| `loop` | `off` holds the last drawing; `loop` starts the run again; `pingpong` goes back and forth. The run is from the first drawing to the end of the last one's hold (the last is held as long as the one before it). |
| `loopTimes` | How many times the run plays, then the drawing last shown holds; 0 (the default) = until the layer ends. |
| `loopStepX`, `loopStepY` | With `loop`: how far each repeat sits from the one before, in the drawing's own px. Draw the walk travelling across its canvas with the planted foot fixed, then set the step to one stride: the figure walks on and its feet never slide. It turns and scales with the layer. |

```python
walk = drawing("walk", w=900, h=600, x=300, y=800, eachFrame=True, loop="loop", loopTimes=6, loopStepX=240)
for i in range(8):                                   # 8 drawings on twos: a 16-frame cycle, played 6 times, 240 px on each time
    ink = walk.frame(i * 2).paint()
    ...                                              # the pose of drawing i, travelling right across the canvas
```

**The walk's numbers.** One cycle is two steps (left, right). Call S the stride: how far the body travels in one
cycle; that is `loopStepX`. With N drawings in the cycle, drawing i's hip sits `S · i / N` further on than drawing 0's.
Each foot is planted for half the cycle (it doesn't move on the canvas while planted) and swings forward by S in the
other half; the second foot does the same half a cycle later and **half a stride (S / 2) further on**. At a contact
pose the front foot is S / 4 ahead of the hip and the back foot S / 4 behind. The last drawing's planted foot then
lands exactly where the next repeat's first drawing has it (the repeat sits S on), so nothing slides. Forgetting the
second foot's S / 2 leaves its leg stretched back in every repeat after the first; check two repeats on a sheet
(`look_frame` `what: "sheet"` across two cycles).

On the screen they are the drawing layer's **Loop**, **Times** and **Step across / Step down** (Timing); agents
`set walk loop "loop"`, `set walk loopTimes 6`. A layer moving at a steady speed (a key on `x`) with a walk drawn in
place is the other way; the step suits a walk drawn with the feet planted. `look_drawing frame=N` says which drawing
shows at N and when it is a repeat.

**Boil** (lines that shimmer while held): 2 or 3 drawings of the same strokes, each with `jitter` (Scatter) a little
above 0 and the points moved a px or two at random, on twos with `loop="loop"`. Each stroke's seed comes from its
id, so every drawing scatters differently. A painting (a painted fill) boils with `frame.add` on the painting
(`inspect_guide drawing`).

## Stepped timing

- **Drawings:** each drawing is held until the next, so "on twos" is drawings at frames 0, 2, 4 …; "on threes" is 0, 3, 6.
  The drawing rate is the composition's `fps` divided by the hold: 12 drawings a second is on twos at 24 fps or on
  threes at 36 fps, and at 30 fps on twos gives 15 a second. The composition's `fps` is only what you set (default
  30); nothing changes it for you. A brief asking for "12 drawings a second and at least 30 fps" fits 36 fps on threes
  (a 36 fps file plays everywhere) or 30 fps with drawings at frames 0, 2, 5, 7, 10 … (holds of 2 and 3 in turn).
  More frames a second means more pictures to make: every frame of a Drawn so far key is its own picture.
  `frame.hold frames=N` changes how long one shows and shifts the later ones. The last drawing is held to the layer's end
  (`end`); add a drawing after it to end a hold.
- **Other layers:** the `hold` ease makes any field jump at the next key instead of travelling: `layer.key("x", {0: 100, 0.2: 300}, ease="hold")`
  steps a layer; keys every 2 frames with `hold` give a stepped move. `linear` between keys is smooth motion.
- A drawing layer's own keys (opacity, position, scale) work like any layer's.

## Paint layers across drawings

1. Draw the lines on one paint layer ("Ink", a new drawing's first), add a second ("Colour") and move it below the lines.
2. Lock the line layer before colouring, so a fill or stroke can't land on it by mistake.
3. Fill "Colour" up to the lines: by default the fill stops at the lines of all visible paint layers.
4. Go to the next drawing (`frame` on `paint.stroke` / `paint.fill`, with `layer` = Colour's key). The same two layers
   are there, empty or copied; on the screen "Colour" stays highlighted, drawing after drawing.
5. Hiding, locking, blend and opacity apply to every drawing at once, so one eye hides all the colour.

## Frame-by-frame working method

1. Block the motion first: a few key drawings (the extremes), checked with `look_frame` (`what: "sheet"`).
2. Fill the in-betweens with `onion=true`, so each drawing sits between its neighbours.
3. Check the loop: the last drawing must lead into the first. `render_export` with `what: "video"` and watch it.

A look (`look_frame`, a sheet, `run_script`'s `look`, a part of a video) makes only the drawings that show at the moments
it draws, several at once, and under `drawnSoFar` only the pictures of those frames; the first look at a big painted
scene is the slowest (each new drawing is painted once, then kept by its content). The export makes every frame's
painting-on pictures the looks didn't, so the first export after a paint change takes longer than a look.

## Not yet

Auto in-betweening of drawings, and animating a single stroke's own path with keys.
