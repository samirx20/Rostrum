# UI and product animation

How to build screens, cards, devices and product shots from boxes, images, masks, glass and depth, and the script calls that make a whole screen of plain layers fast. Read `start-here` first.
Fragments show how a tool is called; the numbers are placeholders.

## Layout

A layer's `x`, `y` is where its **anchor** sits, in the parent's pixels (`anchorX` / `anchorY` 0–1 across its box;
0 = left / top). A group is the container: its children are placed from the group's own top-left (0, 0).

**Auto layout.** Give a group `layout="row"`, `"column"` or `"grid"` and it places its layers itself, again on every
frame, so a layer that grows (its `w` / `h` keyed) pushes the others along:

```python
with group("list", x=240, y=180, w=600, anchorX=0, anchorY=0, layout="column", gap=18, padding=0, hugWidth=False, hugHeight=True):
    for i in range(4):
        with group(f"card{i}", w=600, h=116, clip=True) as card:
            ...                                    # the card's own layers, placed by hand inside it
    card.key("h", {0.6: 116, 1.5: 372})            # this card opens; the ones under it slide down
```

| Setting | What it does |
|---|---|
| `gap`, `padding` | space between layers (16 px at first), and inside the group's edge (10 px at first, as in a design tool; files made before this keep 0) |
| `justify` | along the line: `start`, `center`, `end`, `between` (row / column) |
| `align` | across the line (or in a grid cell): `start`, `center`, `end`, `stretch` (fills it) |
| `wrap`, `rowGap` | a new line when the next layer doesn't fit (row / column), and the space between lines |
| `columns` | grid: equal columns `gap` apart, rows `rowGap` apart, each as tall as its tallest layer |
| `hugWidth`, `hugHeight` | the group's size follows what is inside it. On by default (as in a design tool): turning auto layout on makes the box grow with its text; turn one off to keep a fixed width or height. Files made before this keep their own size (they are set off) |
| `hugPin` | on (the default): a hugging group grows right and down from its top-left, as a design tool's frame (the left edge of a row, the top of a column; across a row by `align`) |
| a layer's `layoutGrow` | takes this share of the room left along the line (shapes, images, groups) |
| a layer's `layoutApart` | the layout leaves it alone: placed by its own `x`, `y` (a badge on a card) |

**A group's own background.** `background=True` draws a colour box behind the group's layers, as big as the group:
`bgColor` (a dark slate at first), `bgRadius` (corners; half the height or more is a pill), and an optional outline (`bgStroke`,
`bgStrokeColor`, `bgStrokeWidth`). With auto layout and hugging on, the box hugs the layers with the `padding` all
round, so a lower-third is one group: a name with a pill around it that grows with the name. In the settings panel
it is the group's Background section. A hugging group keeps its top-left fixed and grows right and down (`hugPin`, "Keep top-left fixed" in the panel), so a
longer name pushes the pill's right end only. Move the anchor off the middle (`anchorX=1` grows leftward) or turn `hugPin`
off and it grows around its anchor instead. In a script, give the group its anchor (`anchorX=0` as below puts the left
edge at `x`); with the middle anchor the edge is where the group's own `w` × `h` box puts it. Files made before this keep their old look (`hugPin` off) until you turn it on.

```python
with group("lower_third", x=120, y=900, anchorX=0, anchorY=0.5, layout="row", padding=18, hugWidth=True,
           hugHeight=True, background=True, bgColor="#1d4ed8", bgRadius=999):
    text("name", body="Ada Lovelace", size=44)
```

Layout uses each layer's own box (`w` × `h`) before scale and turn: animate `scale` for a pop that doesn't push the
others, `w` / `h` for one that does. A layer before its start time or after its end takes no room. Text boxes are
estimated from size and letters, so a row of texts may sit a little off; put text inside a fixed-size group. While
laid out, a layer's `x` / `y` belong to the layout (setting them is refused, loudly). See it with `inspect_layout`
(each placed layer's x, y and size at a time) and `look_frame` (`what: "sheet"`).

`clip=True` on a group hides children outside its box (a scrolling list, a window). The box is a plain rectangle: for
rounded corners (a phone's screen) give the group a mask with a radius instead, the size of its box:
`screen.mask("screen_round", x=0, y=0, w=390, h=844, radius=56)` (see Masks below). `layer.arrange` moves a layer in the
stack or into another group; `inspect_item` with no `id` lists the tree.

`layer.duplicate target=["card"] args={by_x: 240, times: 7}` makes a row of eight in one change: each copy takes the step (`by_x`, `by_y` px, `by_turn` degrees, `by_scale` as a factor) from the one before, so a ring is `by_turn: 30, times: 11` (put the anchor at the ring's centre first).

### A grid of copies you can find again

Copies are only useful if you know which is which. Two ways, by who makes them:

- **In a script** (re-runnable: a re-run rebuilds the grid and keeps what a person moved): write one function that
  builds one item, and call it in a loop with an id made from its place. Row and column are in the id, so `icon_r1_c2`
  is always the second row's third icon.

  ```python
  def icon(id, x, y, hue):
      with group(id, x=x, y=y, adjust=True, hue=hue) as g:
          shape(f"{id}_bg", w=160, h=160, radius=36, fill="#1f2937")
          ...                                          # the icon's own layers
      return g

  for r in range(3):
      for c in range(3):
          icon(f"icon_r{r}_c{c}", x=300 + c * 200, y=700 + r * 200, hue=c * 40)
  ```

- **With `layer.duplicate`** (one change on the document): `copy_ids` names the copies, `{n}` counting from 1 in the
  order they are made (each one step on from the last, up the stack): `layer.duplicate target=["icon"]
  args={by_x: 200, times: 2, copy_ids: "icon_c{n}"}` gives `icon_c1`, `icon_c2` to the right of `icon`. For a grid,
  duplicate the row's group down the same way (`by_y`, `copy_ids: "row_{n}"`). An id that is already used is refused.

Then stagger them in a reading order: `layer.stagger` with `order: "left_to_right"`, `"top_to_bottom"` or `"centre"`
orders by where each is seen (one that fades or scales in from 0 counts where it sits, its own scale and opacity taken as full).

## Building blocks: a whole screen in a few lines

These script calls make a device and the usual parts of a screen as **plain groups of shapes and texts**, with ids made
from the block's id (`trips_r0_title`, `pay_label`), so each part is moved, keyed, restyled or taken apart afterwards
like anything you made by hand. Every colour and size is a parameter; the defaults are only a neutral start. Each is
placed by its top-left `x`, `y` in the parent's px (the screen's, inside `with scr:`).

| Call | Makes |
|---|---|
| `scr = device(id, kind="phone" \| "laptop" \| "browser", x=, y=, w=, h=, body=, screen=, url=)` | the device from shapes, centred on (x, y), and returns its **screen**: a clipped group (rounded by a mask) whose px start at the screen's top-left. `scr.w`, `scr.h` are its size. `layer(id)` is the whole device (move, scale or tilt that). |
| `status_bar(w=, y=0, time="9:41", color=)` | the time on the left, signal, Wi-Fi and battery on the right |
| `nav_bar(title, w=, y=, back=, action=)` | a big title, an optional back label and action word |
| `tab_bar(labels, w=, parent_h=scr.h, active=0, accent=)` | tabs across the bottom, each an icon square and a label |
| `rows = list_rows(rows, x=, y=, w=, row_h=84, avatar=True)` | one group per row (`<id>_r0` …): avatar with an initial, title, detail line, value on the right, divider. A row is a string, `(title, detail)` or `(title, detail, value)`. Returns the row groups, top first. |
| `card(id, x=, y=, w=, h=, title=, detail=, value=, fill=, radius=28, shadow=True)` | a rounded card with text at its top-left and a big value at its bottom-left; make more of its layers inside `with` it |
| `button(label, x=, y=, w=, h=, fill=, outline=False)` | a pill with its label centred (`<id>_bg`, `<id>_label`) |
| `toggle(id, x=, y=, on=False)` | a switch: `<id>_track` and `<id>_knob`; flip it by keying the knob's `x` and the track's `fill` |
| `bars = bars(values, x=, y=, w=, h=, labels=, top=)` | a bar chart standing on its bottom edge (each bar anchored there: a key on `scaleY` from 0 grows it upward). Returns the bars, left first. |
| `counter(id, start, to, at=, duration=, decimals=, prefix=, suffix=, separator=, **text fields)` | one text that counts (below) |

```python
scr = device("phone", kind="phone", x=640, y=540)
with scr:
    status_bar(w=scr.w); nav_bar("Trips", w=scr.w, y=54, action="Edit")
    card("hero", x=24, y=170, w=scr.w - 48, h=200, title="Lisbon dinner", detail="4 people", value="$168.00")
    rows = list_rows([("Ana", "owes you", "$42.00"), ("Ben", "owes you", "$42.00")], y=390, w=scr.w)
    tab_bar(["Home", "Trips", "Friends", "You"], w=scr.w, parent_h=scr.h, active=1)
for i, r in enumerate(rows):                          # stagger the rows in: they are ordinary groups
    r.key("opacity", {1.0 + i * 0.06: 0, 1.4 + i * 0.06: 1}).key("y", {1.0 + i * 0.06: r.y + 30, 1.4 + i * 0.06: r.y})
```

## Counting numbers

A number that counts is **one text** with *Counts a number* on: the engine writes the digits on every frame from its
`count` field, so the look tools and the export show the same number, and the width stays steady with tabular figures.
Never stack a text per value. In a script, `counter("total", 0, 186.4, at=2, duration=1.2, decimals=2, prefix="$",
size=72)` (the text's other fields after the numbers), or on any text: `text("n", counter=True, countDecimals=2,
countPrefix="$", figures="tabular lining").key("count", {2: 0, 3.2: 186.4})`. As an operation, `text.counter` (`from`,
`to`, `at`, `duration`, `ease`, `decimals`, `digits`, `separator`, `prefix`, `suffix`). More steps (it counts, pauses,
counts on): more keys on `count`. The ease of the first key shapes the count (`easeOut` slows into the final value). A
number that should land on a beat: key the end on that time, not the start.

## Density: what makes a screen read as a real product

A screen reads as a real app when it carries the amount of detail a real one does, at every moment the shot shows it.
Techniques to check against, not a style:

- **Fill the screen it opens on.** The first frame of the device is seen longest. Status bar, title, at least one
  card or chart and a list that runs past the bottom edge (the clip cuts it, which says "there is more") read as a
  product; a lone title on white reads as a placeholder. Put the content in place first, then animate the way into it.
- **Several levels of text.** A title, a value, a label and a detail line, in clearly different sizes and weights and
  two or three greys, give a screen its structure. One size and one colour make it a mock-up.
- **Real-looking content.** Names, amounts with cents, dates, counts, avatars with initials. Repeated "Item 1, Item 2"
  reads as a wireframe.
- **Something on every surface.** A card should carry its title and value from the moment it is seen. When a card opens
  into a screen (a shared-element move), the new screen's content fades in while it grows, not after; the empty check
  (`look_frame` `what: "empty"`) names a plain box with nothing on it that is changing size.
- **Edges and depth.** Dividers, a soft shadow under cards, a frosted bar over content that scrolls under it separate the
  layers of the interface the way a real one does.

## Into the screen: the camera on a device

The frame (FRAME.md) is a camera over the comp, so the shot can travel into a device and back like a product film:
`f = frame()`; `f.fit(["phone"], at=0.5)` frames the whole device; `f.fit(["hero_value"], at=3, pad=0.25,
ease="easeInOut")` pushes in on a number as it counts; `f.fit(["phone"], at=5)` pulls back out; `f.cut(at=7,
to="items", items=["rows"])` jumps to a new framing on a beat. Push in on the thing that changes (a count, a toggle, a
chart growing) while it changes, and pull out before the next action happens elsewhere. A slight `tiltY` on the device
group as it enters, settling to 0, makes the screen a physical object; keep it flat while the viewer reads.

## Boxes, images, video

| Layer | Controls |
|---|---|
| `shape` | `shape` rect / ellipse, `w`, `h`, `radius` (corner), `fill`, `stroke`, `strokeColor`, `strokeWidth`. |
| `image` | `src` (relative to the project folder for a file the project holds, e.g. `media/image/…png`; absolute for one kept outside it), `w`, `h`, `fit` cover / contain / stretch, `radius`. |
| `video` | Same, plus `offset` (seconds into the clip), `speed`, `loop` (`off` holds the last frame, `loop` starts again, `pingpong` plays forward and back). Frames are decoded once at the composition's fps; no sound here. |
| `group` | `w`, `h`, `clip`, and its own background (`background`, `bgColor`, `bgRadius`, outline: see Auto layout). A group's opacity, blend, masks and effects apply to it as a whole. |

Every layer also has the transform (`x`, `y`, `scale`, `scaleX`, `scaleY`, `rotation`, `opacity`, anchor), `start` / `end`
(when it exists), `blend` (17 modes) and colour effects (adjust, levels, curves, LUT): see the guide `colour-and-blending`.

## Masks

A mask is the part of the layer that shows, in the layer's own px from its top-left. `mask.add` (or `item.mask(id, ...)`
in a script): `shape` rect / ellipse, `x`, `y`, `w`, `h`, `radius`, `feather` (soft edge, px), `invert`, `angle`.
A `w` or `h` of 0 shows nothing (inverted: all). Several masks on one layer intersect. A feathered rectangle turned by `angle` and moved across is a soft diagonal wipe.

```python
panel.mask("open", x=0, y=0, w=0, h=300, radius=24).key("w", {0.2: 0, 0.9: 640}, ease="easeOut")
```

A mask travels with its layer. For a layer that moves through a fixed edge, put it in a `clip` group and animate the layer
inside.

### Track mattes

A track matte uses another whole layer as the mask: its shape, letters or picture, animated with its own keys. Set
`matte` on the layer to show (the id of a layer in the same group or comp that draws something: not the Frame, which draws no picture; the Track matte list leaves it out; on the screen the list starts with the layer just above, then the nearest ones) and `matteMode`:

| `matteMode` | The layer shows |
|---|---|
| `alpha` | where the matte layer is drawn |
| `alphaInverted` | where it isn't |
| `luma` | as bright as the matte layer is (white = fully, black = not) |
| `lumaInverted` | as dark as it is |

The matte layer is not drawn on its own; it moves, scales and fades like any layer, and the matted layer follows that.
Two layers may share one matte. The matted layer may be a **group** too (the whole group, its children and their effects, shows
only through the matte), also inside another group and with a matte that moves; a group may be the matte (its children
together are the shape). Both were drawn and checked. A matte layer can be a shape, path, text, image, video, drawing or a group of these, but
has no effects, masks or tilt of its own (refused by name). `look_at` and the motion checks list it as "drawn only as
the track matte of …", and a `matte` id that is no layer beside it is named there and refused by the engine.

```python
picture.set(matte="title", matteMode="alpha")          # the picture seen through the title's letters
title.key("scale", {0.0: 0.9, 1.2: 1.0}, ease="easeOut")    # the matte animates as usual
```

## Glass, blur, shadow, glow

Effects are a layer's look, in order (`effect.add`, or `item.effect(type, id, ...)`).

| Effect | Controls |
|---|---|
| `backdrop` (frosted glass) | Blurs what is **behind** the layer inside its box and corner radius. `radius` (blur), `fillAmount` (how much of the layer's own look shows over the glass: a pale fill at 0.25 reads as frosted), `saturate`, `brightness`. |
| `blur` | `radius` blurs the layer itself. |
| `shadow` | `dx`, `dy`, `radius` (softness), `color`, `strength`. |
| `glow` | `radius`, `strength`, `ownColor` or `color`. |
| `gradient` | Fills the layer instead of its colour: `style` linear / radial / conic, `angle`, `cx`, `cy`, `color1`, `color2`, optional middle colour. |

```python
card = shape("glass", shape="rect", w=520, h=320, radius=32, x=960, y=540, fill="#ffffff")
card.effect("backdrop", id="frost", radius=40, fillAmount=0.2, saturate=1.4)
card.effect("shadow", id="lift", dy=30, radius=60, strength=0.4)
```

Glass needs something behind it to blur: check with `look_frame`, with and without the layers behind. Every effect number
can be keyed (`card.effect(...).key("radius", {...})`).

## Depth and tilt (2.5D)

`tiltX` and `tiltY` (degrees) turn a layer around its horizontal / vertical axis with perspective (1600 px per layer), then
`rotation` and scale apply about the anchor. They are animatable. Tilt is for a flat layer that turns; there are **no 3D
layers** (no real 3D objects, lights or cameras in 2D: that is Rostrum3D). Layers that move in depth because the **frame**
moves are in `frame-parallax-motion-blur`.

Boxes the look tools report (`look_at`) leave tilt out, so a tilted layer's box is approximate: judge a tilt with
`look_frame`.

### A card flip

A card with a front and a back is two groups in one, each turned edge-on in turn with `tiltY` (perspective), so the
back never shows mirrored. At 90° a face is edge-on and invisible, so the swap at that moment can't be seen:

```python
with group("card", x=960, y=540):
    with group("front") as front:
        shape("front_bg", w=360, h=480, radius=24, fill="#f4efe6")
        ...                                            # the front's layers
    with group("back") as back:
        shape("back_bg", w=360, h=480, radius=24, fill="#e0563b")
        ...                                            # the back's layers
front.key("tiltY", {0.5: 0, 0.8: (90, "easeIn")})      # turns away until edge-on
back.key("tiltY", {0.8: -90, 1.1: (0, "easeOut")})     # turns in from edge-on
front.end = 0.8                                        # the front is gone once edge-on ...
back.start = 0.8                                       # ... and the back is there from that moment
```

`tiltX` flips top over bottom the same way. For a flat flip without perspective, key the card's `scaleX` through 0
instead (Stretch X: 100 % → −100 %), swap the faces where it passes 0 (`end` / `start` as above), and give the back
`scaleX=-1` so it reads the right way round. Check the turn on a
sheet over the flip (`look_frame` with `what: "sheet"`).

## Seeing and checking

- `look_frame` (set `width=1920` to check crisp edges), `look_frame` (`what: "sheet"`) over the animation, `look_motion` for what moves.
- `look_frame` (`what: "empty"`) over the whole piece: besides blank and frozen stretches it names a plain box of one colour with nothing on it (6 % of the frame or more) caught while it grows, shrinks, comes or goes: a card that opens before its content arrives.
- `look_at x y time`: the layers whose box covers a point, top first, with values (effects and masks are not counted).
- Animate toward the final layout you already placed: look at the last frame first, then key the way into it.
- Use `value.set` when a person says "make it bigger": a still field changes, an animated one gets a key at `at`.
