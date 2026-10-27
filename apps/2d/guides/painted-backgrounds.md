# Painted backgrounds

How to paint a large background in Rostrum2D with the shared painting kit: a canvas bigger than the frame so the frame
can move over it, split into depth layers so it moves with parallax. This guide is about the tools and ways of working; what
you paint is yours. Read `drawing-and-frame-by-frame` first (strokes, brushes, masks, one call list = one undo step)
and `frame-parallax-motion-blur` (depth).

## The parts

- **Depth layers** are ordinary drawing layers at the composition's top level, each with a `depth`. A layer at depth d
  moves s = 1 / (1 + d) as much as the frame: depth 3 moves a quarter, depth 1 half, depth 0.2 most of the way.
- **Big canvas.** Each depth layer's canvas covers everything the frame ever shows of it over the composition, plus a
  small bleed (24 px). Far layers need less extra room than near ones, because they move less.
- Inside each depth layer, paint layers (`paint.add`) keep passes apart: sky, clouds, a mountain range, haze … Undo,
  hiding (`visible`) and moving work per paint layer.

## On the screen: Set depth

Paint first, then set depths: select first, then act.

1. Select a drawing in the timeline or on the canvas. The settings panel shows **Set depth ▾** at its top.
2. Pick **Far** (depth 3), **Middle** (1) or **Near** (0.25). The drawing moves to that depth, staying where it shows at
   the playhead, and while the frame moves its canvas grows where it must to still cover everything the frame shows of
   it (a canvas that covers already is left as it is: nothing painted is ever cut off). Do the same for each drawing. One pick is one change: **Ctrl+Z** takes it
   back. For another value pick **Other depth…**: a small box opens under the button; type or drag the number
   (0 = on the frame's plane, higher = farther) and the drawing moves as it changes. Click away or press Enter to
   keep it (one change), Esc to take it back.
3. Every scene has its frame, so **Set depth** is there for any drawing of the scene's own layers.

## A background that always covers the frame

The scene's **Background** colour always fills the frame. For a picture, a gradient or a painted background there are
two tools, by what you want:

- **It moves with the frame** (no parallax): pick it, More › **Stick to the shot**, then **Fill the frame**. It covers the frame
  at every moment.
- **It is part of the world** (with or without depth): pick it, More › **Cover the frame's move** (there while the frame
  moves: keys or a ride). It is sized and placed at its depth to cover everything the frame shows of it over the whole
  piece, plus 24 px. A picture, shape or group is scaled evenly and keeps its turn and stretch; a drawing's canvas
  grows. Run it again after you change the move. It is for a layer that stays still (not keyed, not pinned); a text has
  no size of its own.

**The warning band.** With such a layer picked (one that covers the whole frame at some moment while its own size holds still; a bar or wipe growing through the frame gets no band), a striped amber band
lies inside each edge the frame sees past at another moment, with when it starts: "shows past the right edge from
3.2 s". Cover the frame's move takes the band away. It is not shown while playing or looking through the frame.

**Fill the frame** on a layer in the world covers the frame where it is at the playhead only; while the frame moves the
status line says so ("covers the frame at 2.0 s only; Cover the frame's move covers the whole move").

To split one painting into depth layers, pick its strokes with a lasso (**Ctrl**+drag, see `drawing`) and move them
with `background.move` (below).

## The operations (each one call = one undo step; GUI, script and MCP use the same ones)

| Operation | Does |
|---|---|
| `background.add` on a composition, `depths: [3, 1, 0.25]` | Adds one drawing layer per depth, far to near, at the bottom of the stack (or at `index`), named Far / Mid / Near (or `names`), each sized and placed to cover the frame's whole move at its depth. Key the frame first. |
| `background.fit` on a scene's own sized layers (Cover the frame's move) | Makes each cover everything the frame shows of it at its depth over the whole piece (after you changed the move or the depth). A drawing's canvas grows (never shrinks; strokes keep their place in the composition); a picture, shape, path, group or video is scaled evenly and moved, keeping its turn and stretch. Needs a frame that moves; refused for a text, a pinned layer (use `layer.fill_frame`) and a keyed one. |
| `background.move` on paint layers or strokes, `into: <drawing layer>` | Moves them into another drawing layer, keeping where they sit in the composition (points and sizes are converted). A paint layer moves whole (refused for a layer with several drawings: move its strokes instead); strokes go into a paint layer of the same name there (made if missing) or into `paint`. Masks the strokes use come along. |

A drawing is at most 8192 px a side; `background.add` / `background.fit` refuse (and say why) when a layer would need more:
give it a larger depth, a shorter move, or split it.

Painting on a background layer grows it in any direction, like any drawing: paint past its edge and the canvas gets
bigger (in 256 px steps), nothing already painted moving on screen. A script's strokes and fills grow it the same way
when the script runs, so `w`, `h` in `drawing(...)` are a starting size, not a crop: nothing a script paints is cut off
(past 8192 px a side the run is refused, naming the drawing). Its picture holds only what is painted, so a wide
sky with a few clouds costs the clouds. At 8192 px a side a stroke that needs more starts a new drawing at the same
depth just above it ("'Far' is at its largest; this stroke started 'Far 2'"), one undo step with the stroke.

## Seeing it

| Tool | Shows |
|---|---|
| `look_drawing (what "tiles") layer` | The whole canvas cut into labelled tiles (A1, B1 … about one frame each, or `tiles: [cols, rows]`), with the frame drawn on it: solid = first frame, dashed = last frame, thin = everything it shows over the shot. |
| `look_drawing (what "tiles") layer tile: "B2"` | One tile close, with a canvas-pixel grid to place strokes (`grid: 0` to judge texture). The reply gives the tile's box in canvas px. |
| `look_drawing` (`what: "depths"`) | Every drawing layer by depth: how much it moves, its canvas, and whether it covers the frame's move, in words ("312 px short on the right from 1.7 s"). |
| `look_drawing` (`zoom`, `crop`, `paint`, `sampling`) | Any box of a layer, a part at 100 % (`crop: [x, y]`, to judge grain), or one paint layer alone. `look_drawing` (`what: "at"`) / `look_drawing` (`what: "landed"`) as for any drawing. |
| `look_frame`, `look_frame` (`what: "sheet"`) | The layers together, through the frame, rendered by the engine: what the film shows. Check the first and last frame of the move. |

Coordinates in strokes are the layer's own canvas px. With scale 1 (what `background.add` sets), canvas px =
composition px minus the canvas's top-left; the reply of `look_drawing` (`what: "tiles"`) and the layer's `x`, `y`, `w`, `h` give it.

## The brushes for this work

Every setting is listed by `inspect_operations name: stroke.add`. What each does on a big canvas:

- `block` lays square-ended, even paint: covering ground fast, opaque bases, big shapes.
- `flat` is a wide brush that turns with the stroke: horizontal sky and water passes, planes of a rock or a slope.
- `bristle` leaves dry streaks: foliage, grass, cloud edges, a reflection dragged down.
- `chalk` + `grain` breaks up on the paper's tooth: rough surfaces, light catching a texture.
- `round` with `hardness` 0 is a soft airbrush: glows, haze, mist; with `mode: add` it builds light.
- `line` is a crisp thin mark: glints, the waterline, wires.
- `color_jitter` / `hue_jitter` vary each dab's colour; `jitter` scatters dabs off the path; `size_pressure` with
  pressure falling along the points tapers a stroke (a blade of grass, a fir tip).
- `smudge` + `wet` drags paint already on the layer; it also drags transparency, so blend over an opaque base. To melt
  bands together (a sky), use `wet=1` (it then lays no colour of its own) with a soft `round` tip, strokes along the
  bands; below 1 the brush also lays its own colour, and a `bristle` tip drags it in lines, which reads as streaks.

## Washes, glazes and an inked line

How watercolour-and-ink painting works with the kit; what to paint and in which colours is yours.

- **Toned paper.** A drawing is see-through, so whatever is under it is the paper. A paint layer's `ground` makes the
  paper part of the painting: the layer starts filled with that colour, opaque, and its strokes go on it. Multiply
  glazes then darken the paper itself, and granulation settles in it. A light ground keeps the lights of the paper; a
  dark or blue-grey ground starts the picture in the dark, and the lights are then painted in (screen / add) rather
  than left as bare paper. Put the ground on the bottom paint layer, with the lines on a layer of their own above it:
  `paint.fill` finds its area from the visible layers' paint and leaves a toned layer out (it covers everywhere, so
  it bounds nothing); `edges: "layer"` naming the toned layer itself fills it whole.
- **Layer order.** The usual order of a wash painting: ground (or paper) → big washes over whole areas → glazes that
  deepen values where the shadows are → the darkest darks → the ink line → lights last in `screen` or `add` (a lamp,
  a glint), because light laid in multiply can never get lighter than what is under it.
- **Glazing.** `mode: "multiply"` darkens what is under it by the stroke's colour: a second glaze over the first is
  darker again, and the hue of each stays (a blue over a blue goes deeper blue, not grey). `normal` paint at partial
  opacity instead mixes toward its own colour, which lifts darks and greys complementary colours. Several thin
  multiply glazes go deeper and cleaner than one opaque stroke; low saturation glaze colours grey the picture as they
  stack.
- **Wet-on-dry and wet-in-wet.** Each stroke is laid when it is done, like paint on paper that has dried: strokes that
  overlap show both edges (wet-on-dry). For wet-in-wet, where colours melt into each other, lay soft (`hardness` low)
  strokes, or blend them afterwards with `smudge` + `wet` on the same layer (it drags the paint, so work over the
  ground or an opaque base).
- **How a wash dries.** `edge_darken` lays more pigment in a rim just inside each stroke's edge, as a wash does when its
  water pulls pigment to the wet edge; it shows most on firm edges (`hardness` 0.5 and up) and barely on very soft
  ones. Overlapping strokes each keep their own rim, which is how separate passes read as separate. `granulation`
  lays more paint in the paper's valleys, a speckle that follows the `paper` and `paper_scale` and stays put on the
  canvas; it reads on flat areas and on a dark ground.
- **A line that reads as inked.** A ruled line has one width and a perfect path. A hand's line drifts, swells and
  loads: `wobble` drifts the path smoothly (around 0.2-0.5 of the size reads as a confident hand; jittering the
  points yourself gives a jagged line instead), `swell` varies the width along it without pressure in the points,
  `taper_start` / `taper_end` point its ends and `pool` makes the ends carry more ink (together: pointed, but loaded
  where the brush touched down). A little `grain` breaks the edge on the paper's tooth (dry brush); a `bristle` tip
  splits into hairs. Points with pressure still work and take precedence in feel: `size_pressure` follows them.

## Ways of working (techniques, not rules)

- **Plan the move first.** Key the frame, then `background.add`; check with `look_drawing` (`what: "tiles"`) which parts each layer
  shows at the start and end. Detail goes where the frame sees.
- **Block in big shapes** with large opaque strokes before any detail; a base that covers the whole shape stops sky
  showing through gaps between texture strokes later. Clip a shape with a paint mask for a clean silhouette and let
  strokes cross it where the edge should be soft.
- **Ridges and silhouettes in one call.** A filled polygon is a fill: `fill.add {target: <paint layer>, points: [[x, y,
  0], …], color}` (in a script `ink.fill([(x, y), …], color="#2a2340")`), sharp and flat, in painting order with the
  strokes. For a painted edge instead, make the ridge's outline a paint mask (`frame.paintmask(points)` in a script,
  `paintmask.add`) and lay a few broad strokes with `mask=` its id: they fill the shape and keep the brush's texture.
  Either is one item instead of a hundred thin strokes.
- **Values far → near.** Look at the values (`see.values` in the kit, or squint at `look_frame` small): planes further
  back usually sit closer to the sky's value and colour; the nearest plane carries the darkest darks and strongest
  contrast. Decide this for your picture; it is a lever, not a law.
- **Atmospheric depth.** Soft, low-opacity horizontal passes of the horizon colour over the base of a far range, a
  touch of mist where hills meet water: they separate planes without outlines.
- **Edges.** Hard where you want the eye (a lit ridge, a silhouette against the sky), lost where planes melt into haze.
  Masks give hard edges; soft round strokes and bristle crossing a mask's line give lost ones.
- **Texture passes last**, on their own paint layer, so they can be hidden or redone: grass flicks, ripples, needles.
  Vary sizes, angles and spacing; strokes in even rows or columns read as stripes (stagger where each row starts).
- **Light.** Decide where it comes from and put rim light only on the edges that face it.
- **Check at screen size.** Tiles and zooms are for placing; the picture is judged in `look_frame` at the size it will
  be seen, at the first and last frame of the move.
- **Splitting for parallax.** Paint straight into the right depth layer, or paint flat and then `background.move` each
  paint layer (or a set of strokes) into its depth. What sits in front of something else must not be cut off where
  the layer behind was never painted: paint the far layer on under where the nearer ones will be, because the frame
  slides them apart as it moves. `look_drawing` (`what: "depths"`) says if a layer stops short.

## A repeating painted ground

For a ground that goes on and on (paper grain, a field of grass, rain, a patterned wall), paint one small piece and let
it repeat, rather than painting a huge canvas:

- Make a **seamless painting** (`painting.add {w: 256, h: 256}`: blank on its own, it starts seamless) and use it on a
  shape with `fit: "tile"` (`layer.fill {type: "painted", painting, fit: "tile", scale}`); on the screen: click the **Fill** swatch and pick the brush, the last of the seven kind icons, whose name **Painted** shows under the row, then **Tile** under Fit). Every tile is the same
  painting, so a stroke shows in all of them.
- **Paint across the edges.** A stroke that leaves the painting comes back on the opposite side, so the seam is painted
  over like any other place. Strokes that stop short of an edge leave the edge bare in every tile: an even band where
  the tiles meet is how a repeat gives itself away.
- **Break the grid.** Big shapes the size of the painting repeat visibly; keep marks well under its size, vary their
  angle, size and spacing, and spread them across the corners as well as the middle.
- **Judge the repeat**, not the piece: `look_painting {painting, repeats: 1}` shows it 3 × 3; `look_painting` (`what: "facts"`) says
  whether the edges meet. Then `look_frame` at the size it will be seen.
- **Let it move.** `driftX` / `driftY` (px per second) slide the tiles for ever (rain, clouds, a scrolling grain);
  `rotation` turns the whole tiling. These belong to the layer's painted fill, so set them with `layer.fill` (`layer.fill {driftX: 30}` on the shape), never `painting.set`, which refuses them; on the screen they are **Drift** and **Rotation** under the fill's Tile fit.

## Not yet

- The painting kit renders a whole canvas to look at a tile; tiles are crops of it. Very large canvases (above
  ~4000 px) are slower to look at than a frame-sized one.
- A stroke with `smudge` + `pickup` reads the layers below it; after `background.move` it reads its new layers.
- `background.move` keeps rotation and tilt of drawing layers out of the conversion (use scale and position only).
