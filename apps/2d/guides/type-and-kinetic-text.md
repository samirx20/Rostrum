# Type and kinetic text

How to set type and make it move with the tools Rostrum2D has. Read `start-here` first (ids, keys, `run_script`).
Fragments show how a tool is called; words, sizes, times and eases are placeholders for your own decisions.
Ease behaviour is in `easing-and-overlap`.

## A text layer's controls

Make one with `text("title", body="…")` in a script, or `layer.add type=text`. Change it with `text.set`. Every control
below is a field (`inspect_item id=title` lists them with what is valid right now).

| Field | What it does |
|---|---|
| `body`, `size` (px), `color` | The words, how big, what colour. |
| `font` | A family name. An unknown one is refused when the scene loads, and the reply names the families that exist. |
| `weight`, `stretch` | The variable font's weight (`wght`) and width (`wdth`, in %). |
| `slant`, `grade` | The font's `slnt` and `GRAD` axes, set only when not 0. |
| `axes` | Any other axis by tag: `"XTRA 468, CASL 1"`. It wins over the named fields. An axis the font lacks is refused; a value out of range is clamped. |
| `tracking` (em), `lineHeight`, `align`, `boxWidth` | Spacing between letters, line spacing, left / center / right, wrap width (0 = one line). |
| `stroke`, `strokeColor`, `strokeWidth` | An outline on the letters. |

**Optical size** (`opsz`) is set for you: it follows `size`, held to 8–144, so a big title uses the font's display design
and small text its text design. To pin it, name it yourself in `axes`: `axes="opsz 14"`.

**Animatable:** every number and colour field above (`size`, `weight`, `stretch`, `slant`, `grade`, `tracking`,
`lineHeight`, `color`, `strokeWidth` and the transform). Not animatable: `body`, `font`, the type switches, `letterDelay`,
`letterSeed`, `boxWidth`. `inspect_operations name=key.add` lists them.

```python
t = text("head", body="Words", size=180, weight=300, x=960, y=500)
t.key("weight", {0.0: 300, 0.8: 800}, ease="easeInOut")      # a variable-font weight change on a held headline
t.key("tracking", {0.0: 0.1, 0.8: 0.0}, ease="easeOut")
```

## OpenType features

| Field | What it does |
|---|---|
| `ligatures` | Joined letters such as fi, fl, where the font has them (on by default). |
| `figures` | `default`, `proportional lining`, `tabular lining`, `proportional old-style`, `tabular old-style`. Tabular numbers all have one width (they line up in columns, and a changing number does not jiggle). |
| `smallCaps` | The font's own small capitals (`smcp`). Refused if the font has none. |
| `features` | Any OpenType tags: `"ss01 ss03 salt"`, `"cv05=2"`, `"-kern"` (a later tag wins). A tag the font lacks is refused, naming the layer, the field and the features the font has. |

Check a feature by looking: `look_frame` at full width (`width=1920`) on the glyphs it should change.

## Per-letter animation

`letterDelay` (seconds, not animatable) makes each letter (or word) play the layer's own keys that much later than the one
before. 0 = the layer moves as one.

| Field | What it does |
|---|---|
| `letterDelay` | Seconds between one letter's start and the next. |
| `letterSplit` | `letters` or `words`. |
| `letterOrder` | `forward`, `backward`, `center`, `random`. |
| `letterSeed` | Which random order (same on every machine). |

What the keys do per letter: keyed `x` / `y` move each letter from the layer's still `x` / `y`; keyed `rotation`, `scale`,
`stretch`, tilt and `opacity` apply about each letter's own centre; keyed colour, outline colour and width are per letter.
A gradient spans the whole text. With letter animation on, a `boxWidth` other than 0 is refused (no wrapping yet).

```python
t = text("head", body="Rostrum", size=200, x=960, y=540, letterDelay=0.04, letterOrder="forward")
t.key("opacity", {0.2: 0, 0.6: 1}, ease="easeOut")
t.key("y", {0.2: 580, 0.8: 540}, ease="snappy")          # each letter plays these 0.04 s after the one before
```

For different timing per word you can also make one text layer per word and drive the start from a loop
(`0.3 + i * step`, explicit ids so a re-run finds them); `look_motion` prints how much the entrances overlap.

## Gradient-filled letters

A `gradient` effect on a text layer fills its letters instead of the plain colour: `style` linear / radial / conic, `angle`,
`cx`, `cy`, `color1`, `color2`, optional `middle` with `color3` at `mid`. Numbers and colours animate.

```python
t.effect("gradient", id="fill", style="linear", angle=90, color1="#ffffff", color2="#8899ff")
```

Other effects work on text too: `glow`, `blur`, `shadow`, `backdrop` (see `ui-and-product-animation`). Effects have keys:
`t.effect("glow", id="halo", radius=0).key("radius", {1.0: 0, 1.6: 60})`; `look_motion` names it `halo.radius`.

## Reveal with a mask

A mask is the part of the layer that shows, in the layer's own pixels from its top-left (`mask.add`, or `t.mask(...)` in
a script): `shape` rect / ellipse, `x`, `y`, `w`, `h`, `radius`, `feather`, `invert`, `angle`. All numbers animate.

```python
t.mask("reveal", x=0, y=0, w=0, h=300).key("w", {0.3: 0, 1.0: 1400})
```

A mask moves with its layer. To move a layer *through* a fixed edge, put it in a group with `clip=True` and animate the
layer inside it. Masks cut before effects, so a glow cannot spill past a mask.

## Text on a path

The fields `path`, `pathOffset`, `pathAlign`, `pathOverflow` exist on a text layer; the guide for them is
`text-on-a-path` (not yet: S10, Team Sam).

## Fonts

A scene can name project fonts (absolute file paths), which win over the app's fonts. Not yet: a tool that lists the
installed families. The list comes back in the engine's scene reply and in the refusal when a name is wrong.

## Check loop (every pass)

1. `run_script` (same `name`, explicit ids).
2. `look_motion`: moves, overlaps, holds, layers not on screen at the end, keys that do nothing.
3. `look_sheet` over the whole thing; `look_frame` at the landing times and at a hold (`width=1920` for type edges).
4. `look_at x y time`: which layers cover a point, top first (boxes are approximate; text width is estimated).
5. Then `render_video`.

If a person moved something, a re-run reports it as held back. Leave it unless they asked you to put it back.
