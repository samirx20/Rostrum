# UI and product animation

How to build screens, cards, devices and product shots from boxes, images, masks, glass and depth. Read `start-here` first.
Fragments show how a tool is called; the numbers are placeholders.

## Layout

A layer's `x`, `y` is where its **anchor** sits, in the parent's pixels (`anchorX` / `anchorY` 0–1 across its box;
0 = left / top). A group is the container: its children are placed from the group's own top-left (0, 0).

**Auto layout.** Give a group `layout="row"`, `"column"` or `"grid"` and it places its layers itself, again on every
frame, so a layer that grows (its `w` / `h` keyed) pushes the others along:

```python
with group("list", x=240, y=180, w=600, anchorX=0, anchorY=0, layout="column", gap=18, padding=0, hugHeight=True):
    for i in range(4):
        with group(f"card{i}", w=600, h=116, clip=True) as card:
            ...                                    # the card's own layers, placed by hand inside it
    card.key("h", {0.6: 116, 1.5: 372})            # this card opens; the ones under it slide down
```

| Setting | What it does |
|---|---|
| `gap`, `padding` | space between layers, and inside the group's edge |
| `justify` | along the line: `start`, `center`, `end`, `between` (row / column) |
| `align` | across the line (or in a grid cell): `start`, `center`, `end`, `stretch` (fills it) |
| `wrap`, `rowGap` | a new line when the next layer doesn't fit (row / column), and the space between lines |
| `columns` | grid: equal columns `gap` apart, rows `rowGap` apart, each as tall as its tallest layer |
| `hugWidth`, `hugHeight` | the group's size follows what is inside it |
| a layer's `layoutGrow` | takes this share of the room left along the line (shapes, images, groups) |
| a layer's `layoutApart` | the layout leaves it alone: placed by its own `x`, `y` (a badge on a card) |

Layout uses each layer's own box (`w` × `h`) before scale and turn: animate `scale` for a pop that doesn't push the
others, `w` / `h` for one that does. A layer before its start time or after its end takes no room. Text boxes are
estimated from size and letters, so a row of texts may sit a little off; put text inside a fixed-size group. While
laid out, a layer's `x` / `y` belong to the layout (setting them is refused, loudly). See it with `inspect_layout`
(each placed layer's x, y and size at a time) and `look_sheet`.

`clip=True` on a group hides children outside its box (a scrolling list, a window). `layer.arrange` moves a layer in the
stack or into another group; `inspect_item` with no `id` lists the tree.

## Boxes, images, video

| Layer | Controls |
|---|---|
| `shape` | `shape` rect / ellipse, `w`, `h`, `radius` (corner), `fill`, `stroke`, `strokeColor`, `strokeWidth`. |
| `image` | `src` (absolute, or relative to the project folder), `w`, `h`, `fit` cover / contain / stretch, `radius`. |
| `video` | Same, plus `offset` (seconds into the clip), `speed`, `loop`. Frames are decoded once at the composition's fps; no sound here. |
| `group` | `w`, `h`, `clip`. A group's opacity, blend, masks and effects apply to it as a whole. |

Every layer also has the transform (`x`, `y`, `scale`, `scaleX`, `scaleY`, `rotation`, `opacity`, anchor), `start` / `end`
(when it exists) and `blend`: `normal`, `screen`, `add`, `multiply`, `overlay`, `soft-light`.

## Masks

A mask is the part of the layer that shows, in the layer's own px from its top-left. `mask.add` (or `item.mask(id, ...)`
in a script): `shape` rect / ellipse, `x`, `y`, `w`, `h`, `radius`, `feather` (soft edge, px), `invert`, `angle`.
Several masks on one layer intersect. A feathered rectangle turned by `angle` and moved across is a soft diagonal wipe.

```python
panel.mask("open", x=0, y=0, w=0, h=300, radius=24).key("w", {0.2: 0, 0.9: 640}, ease="easeOut")
```

A mask travels with its layer. For a layer that moves through a fixed edge, put it in a `clip` group and animate the layer
inside.

### Track mattes

**Not drawn yet (KNOWN OPEN, H14):** the fields and checks below exist, but the engine refuses a layer with a `matte` when it draws, because the renderer does not apply the matte yet. Use a mask meanwhile.

A track matte uses another whole layer as the mask: its shape, letters or picture, animated with its own keys. Set
`matte` on the layer to show (the id of a layer in the same group or comp) and `matteMode`:

| `matteMode` | The layer shows |
|---|---|
| `alpha` | where the matte layer is drawn |
| `alphaInverted` | where it isn't |
| `luma` | as bright as the matte layer is (white = fully, black = not) |
| `lumaInverted` | as dark as it is |

The matte layer is not drawn on its own; it moves, scales and fades like any layer, and the matted layer follows that.
Two layers may share one matte. A matte layer can be a shape, path, text, image, video, drawing or a group of these, but
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
layers** (no real 3D objects, lights or cameras in 2D: that is Rostrum3D). Layers that move in depth because a **camera**
moves are in `camera-parallax-motion-blur`.

Boxes the look tools report (`look_at`) leave tilt out, so a tilted layer's box is approximate: judge a tilt with
`look_frame`.

## Seeing and checking

- `look_frame` (set `width=1920` to check crisp edges), `look_sheet` over the animation, `look_motion` for what moves.
- `look_at x y time`: the layers whose box covers a point, top first, with values (effects and masks are not counted).
- Animate toward the final layout you already placed: look at the last frame first, then key the way into it.
- Use `value.set` when a person says "make it bigger": a still field changes, an animated one gets a key at `at`.
