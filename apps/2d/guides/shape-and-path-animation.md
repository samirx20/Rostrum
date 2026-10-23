# Shape and path animation

How to make vector shapes, edit them point by point, combine them, and animate how they are drawn. Read `start-here` first.
A person uses the Pen tool and writes the same path data the operations below write.

## Two layers for vectors

- **`shape`**: a rect or ellipse (`w`, `h`, `radius`, `fill`, outline). Simple, and its size and radius animate.
- **`path`**: any outline. Its one truth is `d`: SVG path data with **absolute** commands only: `M x y`, `L x y`,
  `C x1 y1 x2 y2 x y`, `Z`, in the layer's own px from its box's top-left. `w` and `h` are the box (anchor and gradients use
  it). Bad data is refused, naming what is wrong.

`shape.to_path` turns a shape into a path (same id, place, look, effects, masks, keys; keys on fields a path cannot animate
must be removed first).

## Making a path

In a script:

```python
path("mark", d="M 0 0 L 200 0 L 100 160 Z", fill="#ffffff", x=960, y=540)     # box taken from d
path("burst", d=star(5, 120, 50), x=700, y=500)                                # star(points, outer, inner, rotation)
path("hex", d=polygon(6, 100), x=1200, y=500)                                  # polygon(sides, radius, rotation)
```

`star` and `polygon` give `d` fitted to its box (first tip straight up). With operations (`edit_document`, or what the pen
calls): `layer.add type=path`, then `path.add_point`, `path.set_point`, `path.remove_point`, `path.close`.

| Operation | Does |
|---|---|
| `path.add_point x y` | A corner, or a smooth point with handles `inX inY outX outY` (offsets from the point). Goes after point `after`, or starts a new subpath with `new`, or ends the last open subpath. |
| `path.set_point i` | Moves point `i` and/or its handles. `mirror` keeps the two handles opposite (a smooth point). Points are counted over all subpaths from 0. |
| `path.remove_point i` | Removes it. |
| `path.close` | Closes (or opens, `closed=false`) the subpath of point `i` (the last one by default). |
| `path.fit` | Fits the box to the points; the drawing stays where it is. Refused when `x` or `y` has keys (it would move them). |

Point edits never move the box; run `path.fit` when the drawing has grown past it. A path with no points has no `d` yet.

## Look of a path

| Fields | Does |
|---|---|
| `filled`, `fill`, `fillRule` | Fill on or off, its colour, `nonzero` or `evenodd` (holes). |
| `stroke`, `strokeColor`, `strokeWidth` | The outline, centred on the edge. |
| `cap` butt / round / square, `join` miter / round / bevel, `miter` | Line ends and corners. |
| `dash`, `gap`, `dashOffset` | Dashes in px (`dash` 0 = solid). Animate `dashOffset` to march them. |
| `trimStart`, `trimEnd` | The part of the stroke that is drawn, as fractions 0–1 of its length (subpath after subpath). |

| `taperStart`, `taperEnd`, `widthProfile`, `taperAlong` | A stroke whose width varies (below). |

A `gradient` effect fills the path (with `filled` off it colours the stroke), linear and radial; conic is refused on a path.

## Draw on (trim)

Animate `trimEnd` from 0 to 1 with `stroke` on:

```python
line = path("line", d="M 0 0 C 150 -120 350 120 500 0", filled=False, stroke=True, strokeWidth=10, x=960, y=540)
line.key("trimEnd", {0.2: 0, 1.2: 1}, ease="easeInOut")
line.key("trimStart", {1.6: 0, 2.4: 1}, ease="easeIn")       # then take it off from the other end
```

## Variable width (taper and profile)

An even stroke looks mechanical; a pen or brush line is thin where it starts or lifts and fat where it pushes. With `stroke` on:

- **`taperStart`** 0..1: how much of the line's length the width takes to grow from 0 up to full at the start. **`taperEnd`**
  does the same, shrinking to 0 at the end. `0` = no taper. Both can be keyed.
- **`widthProfile`**: text `"pos,mult pos,mult …"`. `pos` is 0..1 along the line (increasing), `mult` times `strokeWidth`
  (0 or more; above 1 is fatter than `strokeWidth`). Between points the width is smooth. Empty = even. It is a still value (not keyed).
- **`taperAlong`**: `line` = positions measure the whole line; `drawn` = only the part the trim shows, so the taper rides along
  with a draw-on. It only matters once a taper or a profile is set.

Set them in one undoable step with `path.width` (it refuses a stroke that is off, positions that don't increase, a negative
multiplier):

```json
{"op": "path.width", "target": ["swash"], "args": {"taperStart": 0.15, "taperEnd": 0.4, "profile": [[0, 0.6], [0.45, 1.8], [1, 0.3]]}}
```

`even: true` removes the profile. In a script, pass the fields: `path("swash", d=…, stroke=True, strokeWidth=12, taperEnd=0.4)`.

**A calligraphic draw-on:** give the line `taperStart` (a soft entry) and key `trimEnd` 0 → 1 with `taperAlong="drawn"` and
`taperEnd` about 0.2, so the head of the stroke is always a thin point while it travels and the line stays fat behind it.
To lift the pen at the end instead, leave `taperAlong="line"` and key `taperEnd` from 0 up as the draw finishes. Look at frames
mid-draw (`look_frame`) to check the head and the tail read the way you want.

## Combining shapes (booleans)

`path.boolean` combines two or more `path` or `shape` layers (same group or comp) into **one new path**:

```json
{"op": "path.boolean", "target": ["circle", "square"], "args": {"mode": "subtract", "id": "cut"}}
```

`mode`: `union`, `subtract` (the first minus the others), `intersect`, `exclude`. The inputs are removed (one undo step
brings them back); the result sits where they were, with the first one's fill and stroke. A tilted layer cannot be
combined (refused). The curves stay curves.

## Keys on paths

A path layer's transform, opacity, `fill`, `strokeColor`, `strokeWidth`, `dash`, `gap`, `dashOffset`, `trimStart`,
`trimEnd`, `taperStart`, `taperEnd`, `miter` and its shape `d` animate (`widthProfile` does not). `w` and `h` do not (the box stays; the curve may reach outside it).

## Morphing a path

Key `d` with path data at two or more times; between two keys the engine blends the shapes point by point, shaped by
the first key's ease (a spring or bounce overshoots the shape too).

```json
{"op": "key.add", "target": ["mark"], "args": {"prop": "d", "t": 0.5, "d": "M0 0 L100 0 L100 100 L0 100 Z"}}
{"op": "key.add", "target": ["mark"], "args": {"prop": "d", "t": 1.5, "d": "M50 0 L100 100 L0 100 Z", "ease": "snappy"}}
```

In a script: `item.key("d", {0.5: polygon(4, 100, 45), 1.5: star(5, 100, 45)})`.

How the shapes are paired, so you can steer the in-between:

- **Pieces (subpaths) pair in order** and must be as many in both shapes; otherwise the key is refused, naming the
  layer and the two key times. Give a shape an extra tiny piece to match, or morph each piece as its own layer.
- **Segments** are paired one to one. Lines count as straight curves. When one shape has fewer segments, its longest
  segment is halved until the counts match. To choose where the shape bends first, give that key's path data more
  points there (write them in, or add them with `path.add_point` before the shape is keyed and copy its `d`).
- **A closed piece starts where the other's start is nearest**: the start points are lined up to travel the least.
  Draw both shapes in the **same direction** (both clockwise): opposite directions turn the shape inside out half way.
- Open and closed pieces may be paired; the piece closes from half way.

Check the in-between with `look_sheet` over the stretch; the settings panel's "value now" shows the shape of the key that
starts the stretch (the engine draws the blend). The Lottie export holds a morphing path at its first shape and says so.

Other ways to change a shape over time: `scale` / `scaleX` / `scaleY`, `rotation`, a mask, or a rig bind (a path bound
to two bones bends; see `character-rigging-and-lip-sync`).

## A layer riding a path

Any layer (a spark, a pen nib, a car, a group) can ride a path layer beside it (same composition or group), so it sits
on the tip of a line as the line draws on, with no arc-length maths in your script:

```
layer.ride target=spark path=line                 # rides the drawn-on tip (Trim end)
layer.ride target=spark path=line turn=true       # ... and turns with the line's direction
layer.ride target=car path=road at=along along=0  # a set place; key rideAlong 0 → 1 to drive along the whole road
layer.ride target=spark path=                     # stop riding (stays where it was at 0 s)
```

- **Where it sits:** the layer's anchor lands on the path (Anchor X / Y pick which point of the layer that is). Its X, Y
  become an offset from there (layer.ride sets them to 0); key them to bob above the line. On screen the Position row
  then reads **Offset from path** (X, Y).
- **Rides at:** a path set alone (`set ridePath`, or the Ride picker) rides **along**: Along path starts at 0, the path's start, and
  keying it 0 → 1 drives the layer or camera along the path. `layer.ride` with no `at` still rides the drawn-on tip. `end` = the tip of the part drawn so far (key `trimEnd` and the layer travels with the drawing), `start`
  = Trim start (a line drawn off from behind), `along` = `rideAlong` (0 = the path's start, 1 = its end) whatever the trim.
- **The path can move:** reshaping (`d` keys), moving, turning or scaling the path carries the rider with it on every
  frame. A path's tilt is not followed.
- Trails, smears and motion blur see the ride (they sample the same frames).
- A ridden path can't ride a path itself, and a text following a path layer (`text.follow`) can't also ride one.
- **The camera can ride a path too.** `layer.ride target=cam path=road at=along` and key `rideAlong` 0 → 1: where the
  camera looks sits on the path, its own `x` / `y` are an offset, and `turn=true` rolls it with the path's direction.
  `look_sheet` over the shot shows where it is at each time.

## Seeing and checking

- `look_frame` at the extremes, `look_sheet` over a draw-on (the spacing of tiles is the ease).
- `inspect_item id=mark` shows `d`, the box and the operations that fit it now.
- `look_motion layers=[line]` lists `trimEnd` / `dashOffset` moves, peak rates, holds.
- `look_at x y time` tells which layers' boxes cover a point (boxes only, not the curve).

## Not yet

Offset or stroke-to-outline, text to outlines (only through SVG import `text="outline"`).
