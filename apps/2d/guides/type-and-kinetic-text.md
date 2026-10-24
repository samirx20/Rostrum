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
| `font` | A family name: one shipped with Rostrum2D or installed on this computer (`inspect_fonts` lists them). A name that is neither is refused when it is set, never drawn in another font. |
| `weight`, `stretch` | The weight (a variable font's `wght`, any value in its range; a family of separate weights, such as Arial, is drawn in its nearest weight, so use one `inspect_fonts` lists) and the width (`wdth`, in %). |
| `italic` | The family's own italic (on / off). Refused if the family has none. |
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
`cx`, `cy`, `color1`, `color2`, optional `middle` with `color3` at `mid`. Numbers and colours animate. A linear `angle` is
the way `color1` runs to `color2`, as in CSS: 0° bottom to top, 90° left to right, 180° (the default) top to bottom.

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
[text-on-a-path.md](text-on-a-path.md). Easing and timing of the moves: [curve-editor.md](curve-editor.md) and [expressions.md](expressions.md).

## Fonts

Two kinds of font can be named:

- **Shipped with Rostrum2D** (the same on every computer): Inter, Roboto Flex, Recursive, Montserrat, Source Serif 4,
  Fraunces, JetBrains Mono, Caveat. All are variable fonts (any weight in their range); all but Roboto Flex, Recursive
  and Caveat have an italic.
- **Installed on this computer**: Arial, Georgia, Segoe UI and anything the person has installed. Another computer may
  not have them.

`inspect_fonts` (optional `search="serif"`) lists every family with its source, real weights, range and whether it has an
italic. A script can read the same list in Python: `from rostrum2d.fontlist import families`. A font installed while
the app runs shows after a restart.

**A missing font is never swapped.** Setting a font that isn't there is refused at once, naming the closest names. A
project opened on a computer that lacks one of its fonts shows a **Missing font** problem naming every text that uses it
(`inspect_diagnose`, and the Problems chip on the screen). The canvas never goes blank: it draws everything else, and each
such text shows as its own box with a dashed red edge and the font's name (looks and part renders carry a warning too).
A whole-film export refuses, naming the texts, so no file ever goes out with the wrong letters. The fix is one change for
all the texts that use the font: on the screen, the problem's **Use another font** list; for an agent,
`font.replace {from: "Söhne", to: "Roboto Flex"}` (texts and text styles, one undo step). For a piece
that has to open anywhere, use a shipped font. A scene can also name project fonts (absolute file paths), which win
over both.

## Check loop (every pass)

1. `run_script` (same `name`, explicit ids).
2. `look_motion`: moves, overlaps, holds, layers not on screen at the end, keys that do nothing.
3. `look_sheet` over the whole thing; `look_frame` at the landing times and at a hold (`width=1920` for type edges).
4. `look_at x y time`: which layers cover a point, top first (boxes are approximate; text width is estimated).
5. Then `render_video`.

If a person moved something, a re-run reports it as held back. Leave it unless they asked you to put it back.
