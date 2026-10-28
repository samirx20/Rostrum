# Type and kinetic text

How to set type and make it move with the tools Rostrum2D has. Read `start-here` first, and `script-reference` for ids, keys and `run_script`.
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
| `tracking` (em), `lineHeight`, `align`, `boxWidth` | Spacing between letters, line spacing, left / center / right (without a wrap width it also says where `x` is: the left edge, the middle, the right edge; the anchor follows it), wrap width (0 = one line). |
| `stroke`, `strokeColor`, `strokeWidth` | An outline on the letters. |

**Optical size** (`opsz`) is set for you: it follows `size`, held to 8–144, so a big title uses the font's display design
and small text its text design. To pin it, name it yourself in `axes`: `axes="opsz 14"`.

**Animatable:** every number and colour field above (`size`, `weight`, `stretch`, `slant`, `grade`, `tracking`,
`lineHeight`, `color`, `strokeWidth` and the transform). Not animatable: `body`, `font`, the type switches, `letterDelay`,
`letterSeed`, `boxWidth`. `inspect_operations name=key.add` lists them. A number that counts is the `count` field (below).

```python
t = text("head", body="Words", size=180, weight=300, x=960, y=500)
t.key("weight", {0.0: 300, 0.8: 800}, ease="easeInOut")      # a variable-font weight change on a held headline
t.key("tracking", {0.0: 0.1, 0.8: 0.0}, ease="easeOut")
```

## OpenType features

| Field | What it does |
|---|---|
| `ligatures` | Joined letters such as fi, fl, where the font has them (on by default). |
| `figures` | `default`, `proportional lining`, `tabular lining`, `proportional old-style`, `tabular old-style`. Tabular numbers all have one width (they line up in columns, and a changing number does not jiggle). Tabular works on every font: where the font has no tabular numbers of its own (Roboto Flex, the default), every digit is given the widest digit's width, centred in it. The panel's Number style lists only the styles the text's font can do (old-style numbers need a font that has them); a script or agent asking for one the font lacks is refused, naming the features the font has. |
| `smallCaps` | The font's own small capitals (`smcp`). Refused if the font has none. |
| `features` | Any OpenType tags: `"ss01 ss03 salt"`, `"cv05=2"`, `"-kern"` (a later tag wins). A tag the font lacks is refused, naming the layer, the field and the features the font has. |

Check a feature by looking: `look_frame` at full width (`width=1920`) on the glyphs it should change.

## Per-letter animation

`letterDelay` (seconds, not animatable) makes each letter (or word) play the layer's own keys that much later than the one
before. 0 = the layer moves as one. Inside a `row` or `column` such a text takes the room of its one line (it doesn't wrap).
A sentence typed word by word is one text with `letterSplit="words"`; one word in another colour, weight or size is a styled
run of that same text (`body=["Make it ", ("move", {"color": …})]`, guide `styled-words`), never a second text placed beside it.

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
On the screen, each effect setting in the settings panel has its own key diamond, as Position does: click it at the
first moment, move the playhead and type the next value (a blur-in: Blur 30 at 0 s, 0 at 0.6 s).

## Reveal with a mask

A mask is the part of the layer that shows, in the layer's own pixels from its top-left (`mask.add`, or `t.mask(...)` in
a script): `shape` rect / ellipse, `x`, `y`, `w`, `h`, `radius`, `feather`, `invert`, `angle`. All numbers animate. A
mask of `w` or `h` 0 shows nothing of the layer (inverted, all of it), so a wipe keyed from `w` 0 starts hidden.

```python
t.mask("reveal", x=0, y=0, w=0, h=300).key("w", {0.3: 0, 1.0: 1400})
```

A mask moves with its layer. To move a layer *through* a fixed edge, put it in a group with `clip=True` and animate the
layer inside it. Masks cut before effects, so a glow cannot spill past a mask.

## Hand-lettered words

A text layer is typed letters. For words that look written by hand and write on stroke by stroke, paint them instead:
`paint.letters` lays each letter's centre line from a single-stroke font and paints it with any brush on a drawing, in
writing order; key the drawing's `drawnSoFar` 0 → 1 to write them on. How: [painted-backgrounds.md](painted-backgrounds.md)
› Hand-lettered words. They are paint, not text: to change the words, clear that paint layer and letter them again.

## Text on a path

To make a text follow a path layer, use `text.follow` with `path:"<path layer id>"` (a script writes `pathLayer="<id>"`); the text's own `path` field holds raw path data, not a layer id. The fields `pathLayer`, `path`, `pathOffset`, `pathAlign`, `pathOverflow` exist on a text layer; the guide for them is
[text-on-a-path.md](text-on-a-path.md). Easing and timing of the moves: [curve-editor.md](curve-editor.md) and [expressions.md](expressions.md).

## A number that counts

A text can show a number that counts instead of its words: a running total, a price, a percentage. Turn on `counter`
and key `count` like any number; the engine writes the number on every frame, so the canvas, `look_frame` and the export
show the same digits, and the text's box (alignment, auto layout, a group that fits its content) follows the number shown.
A counting text that still has its automatic name is listed as "Counter" ("Counter 2" …), not as the words typed in it; a name you gave it is kept.

| Field | What it does |
|---|---|
| `counter` | On: the text shows `countPrefix`, the number, `countSuffix`; its `body` is not shown. |
| `count` | The number. Animatable: from → to by keys, with any ease. |
| `countDecimals` | Places after the decimal mark (0 to 6; not animatable). The number is rounded to them. |
| `countDigits` | At least this many digits, zeros in front (3: 007), as a scoreboard or an odometer (not animatable). |
| `countSeparator` | The thousands mark: `comma` 1,284.5 · `period` 1.284,5 · `space` 1 284.5 · `none` 1284.5. |
| `countPrefix`, `countSuffix` | Words before and after the number: `"$"`, `" GWh"`, `"%"` (put the space in yourself). |

In one change, from an agent or the panel's operation: `text.counter` with `from`, `to`, `at`, `duration`, `ease` and the
format (`decimals`, `digits`, `separator`, `prefix`, `suffix`). It replaces the `count` keys with two. In a script:

```python
n = text("total", counter=True, count=0, countSuffix=" GWh", font="Inter", figures="tabular lining", size=200, x=600, y=300)
n.key("count", {0.5: (0, "easeOut"), 2.0: (450, "hold"), 2.4: 900})     # several steps: one key per step
```

- **Tabular figures** (`figures="tabular lining"`) give every digit one width, so a centred or right-aligned number does
  not jiggle while it counts. It works on every font: where the font has no tabular numbers of its own (Roboto Flex, the default), every digit takes the widest digit's width, centred in it. With
  proportional figures the box changes width with each digit.
- The anchor decides which side stays put as digits are added: `anchorX=1` with `align="right"` keeps the last digit
  still (a total that grows to the left), `anchorX=0` keeps the first.
- Per-letter animation (`letterDelay`) splits the shown number, so each digit can move on its own.
- With motion blur on (the scene's `shutter`), the number stays sharp: each frame shows its own one number, as in After Effects. Only the text's movement (place, turn, size, fade) blurs.

## Characters that scramble into words

`scramble(id, body, start=, end=, rate=15, chars=None, order="forward", seed=1, **text fields)` in a script: the line's
characters cycle and lock, one by one, into `body` between `start` and `end`. It makes plain layers: a swap set (a group
showing one child at a time) of texts `<id>_0` … `<id>_<n>`, one per step, the last the final words, and keys the
group's `show`. Each character cycles through its own kind (capitals, small letters, digits; spaces and marks stay)
unless `chars` gives the set. `order`: `forward`, `backward`, `center` or `random` (which locks first). Every text
field goes to each step, so they share a place; a mono font keeps the width still. Before `start` the first jumble
shows: `.set(start=…)` on the group hides it until then.

```python
s = scramble("freq", "1420.405 MHZ", start=3, end=4.2, font="JetBrains Mono", size=48, x=960, y=700, align="center")
```

A number that counts (not cycles) is a counter (above).

## Fonts

Two kinds of font can be named:

- **Shipped with Rostrum2D** (the same on every computer): Inter, Roboto Flex, Recursive, Montserrat, Source Serif 4,
  Fraunces, JetBrains Mono, Caveat. All are variable fonts (any weight in their range); all but Roboto Flex, Recursive
  and Caveat have an italic.
- **Installed on this computer**: Arial, Georgia, Segoe UI and anything the person has installed. Another computer may
  not have them.

`inspect_fonts` lists the families shipped with Rostrum2D (the same on every computer) with their real weights, range
and whether they have an italic, and how many are installed on this computer; `search="serif"` (part of a name) lists
the matching ones, installed too, and `all: true` every one. (A scene script can't import modules beyond `math` and `random`: pick the family with `inspect_fonts`, then write its name in the script.) A font installed while
the app runs shows after a restart.

**A missing font is never swapped.** Setting a font that isn't there is refused at once, naming the closest names. A
project opened on a computer that lacks one of its fonts shows a **Missing font** problem naming every text that uses it
(`look_frame` with `what: "diagnose"`, and the Problems chip on the screen). The canvas never goes blank: it draws everything else, and each
such text shows as its own box with a dashed red edge and the font's name (looks and part renders carry a warning too).
A whole-film export refuses, naming the texts, so no file ever goes out with the wrong letters. The fix is one change for
all the texts that use the font: on the screen, the problem's **Use another font** list; for an agent,
`font.replace {from: "Söhne", to: "Roboto Flex"}` (texts and text styles, one undo step). For a piece
that has to open anywhere, use a shipped font. A scene can also name project fonts (absolute file paths), which win
over both.

## Check loop (every pass)

1. `run_script` (same `name`, explicit ids) with `look: true` (or the landing times): a contact sheet and the weakest moments come back in the reply.
2. `look_motion`: moves, overlaps, holds, layers not on screen at the end, keys that do nothing.
3. `look_frame` at the landing times and at a hold (`width=1920` for type edges).
4. `look_at x y time`: which layers cover a point, top first (boxes are approximate; text width is estimated).
5. Then `render_export` with `what: "video"` (it waits for its file in the same call, `wait_s`).

If a person moved something, a re-run reports it as held back. Leave it unless they asked you to put it back.
