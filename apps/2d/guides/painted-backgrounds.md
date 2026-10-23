# Painted backgrounds

How to paint a large background in Rostrum2D with the shared painting kit: a canvas bigger than the frame so the camera
can move, split into depth layers so it moves with parallax. This guide is about the tools and ways of working; what
you paint is yours. Read `drawing-and-frame-by-frame` first (strokes, brushes, masks, one call list = one undo step)
and `camera-parallax-motion-blur` (depth).

## The parts

- **Depth layers** are ordinary drawing layers at the composition's top level, each with a camera `depth`. A layer at
  depth d moves s = 1 / (1 + d) as much as the camera: depth 3 moves a quarter, depth 1 half, depth 0.2 most of the way.
- **Big canvas.** Each depth layer's canvas covers everything the camera ever shows of it over the composition, plus a
  small bleed (24 px). Far layers need less extra room than near ones, because they move less.
- Inside each depth layer, paint layers (`paint.add`) keep passes apart: sky, clouds, a mountain range, haze … Undo,
  hiding (`visible`) and moving work per paint layer.

## On the screen: Set depth

Paint first, then set depths: select first, then act.

1. Make sure the composition has a camera (press **C** in the tool rail).
2. Select a drawing in the timeline or on the canvas. The settings panel shows **Set depth ▾** at its top.
3. Pick **Far** (depth 3), **Middle** (1) or **Near** (0.25). The drawing moves to that depth and is resized so it still
   covers everything the camera shows of it. Do the same for each drawing. One pick is one change: **Ctrl+Z** takes it
   back. For another value, type it in the drawing's **Depth** setting and run `background.fit` (below).
4. Without a camera, **Set depth** is not in the panel. Press **Ctrl+K** and type "set depth": it says why.

To split one painting into depth layers, pick its strokes with a lasso (**Ctrl**+drag, see `drawing`) and move them
with `background.move` (below).

## The operations (each one call = one undo step; GUI, script and MCP use the same ones)

| Operation | Does |
|---|---|
| `background.add` on a composition, `depths: [3, 1, 0.25]` | Adds one drawing layer per depth, far to near, at the bottom of the stack (or at `index`), named Far / Mid / Near (or `names`), each sized and placed to cover the camera's whole move at its depth. Key the camera first. |
| `background.fit` on drawing layers | Resizes a layer to cover the camera's move at its depth again (after you changed the camera or the depth). Strokes keep their place in the composition. |
| `background.move` on paint layers or strokes, `into: <drawing layer>` | Moves them into another drawing layer, keeping where they sit in the composition (points and sizes are converted). A paint layer moves whole; strokes go into a paint layer of the same name there (made if missing) or into `paint`. Masks the strokes use come along. |

A drawing is at most 8192 px a side; `background.add` / `fit` refuse (and say why) when a layer would need more:
give it a larger depth, a shorter move, or split it.

## Seeing it

| Tool | Shows |
|---|---|
| `look_background layer` | The whole canvas cut into labelled tiles (A1, B1 … about one frame each, or `tiles: [cols, rows]`), with the camera's frame drawn on it: solid = first frame, dashed = last frame, thin = everything it shows over the shot. |
| `look_background layer tile: "B2"` | One tile close, with a canvas-pixel grid to place strokes (`grid: 0` to judge texture). The reply gives the tile's box in canvas px. |
| `inspect_background` | Every drawing layer by depth: how much it moves, its canvas, and whether it covers the camera's move, in words ("312 px short on the right"). |
| `look_drawing` (`zoom`, `paint`, `sampling`) | Any box of a layer, or one paint layer alone. `inspect_drawing_at` / `inspect_stroke_landed` as for any drawing. |
| `look_frame`, `look_sheet` | The layers together, through the camera, rendered by the engine: what the film shows. Check the first and last frame of the move. |

Coordinates in strokes are the layer's own canvas px. With scale 1 (what `background.add` sets), canvas px =
composition px minus the canvas's top-left; the reply of `look_background` and the layer's `x`, `y`, `w`, `h` give it.

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
- `smudge` + `wet` drags paint already on the layer; it also drags transparency, so blend over an opaque base.

## Ways of working (techniques, not rules)

- **Plan the move first.** Key the camera, then `background.add`; check with `look_background` which parts each layer
  shows at the start and end. Detail goes where the camera sees.
- **Block in big shapes** with large opaque strokes before any detail; a base that covers the whole shape stops sky
  showing through gaps between texture strokes later. Clip a shape with a paint mask for a clean silhouette and let
  strokes cross it where the edge should be soft.
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
  the layer behind was never painted: paint the far layer on under where the nearer ones will be, because the camera
  slides them apart. `inspect_background` says if a layer stops short.

## Not yet

- The painting kit renders a whole canvas to look at a tile; tiles are crops of it. Very large canvases (above
  ~4000 px) are slower to look at than a frame-sized one.
- A stroke with `smudge` + `pickup` reads the layers below it; after `background.move` it reads its new layers.
- `background.move` keeps rotation and tilt of drawing layers out of the conversion (use scale and position only).
