# Script reference

Every script function and field, and the first-time surprises. Read `start-here` first; how to build a whole film as one
script is in `the-film-as-one-script`, how to place things in `lay-out-a-screen`.

## The document

```
document
  comps
    comp
      layers: shape | text | image | video | path | drawing | rig | group (a group holds layers),
              and each scene's own frame (what the export shows; made with the scene)
        each layer has:
          effects  (blur, glow, gradient, shadow)
          masks    (the part that shows)
          keys     (the animation)
```

- Every part has an **id** (`title`, `bg`, `title.opacity.k200`). Use ids, never names or positions. `inspect_item` with no `id`
  lists them; with an `id` it shows one part's values and the operations that fit it right now. Its keys come as a
  summary per field (how many, first and last time and value); `keys: "all"` lists every key.
- `inspect_operations` lists everything you can do (`text.set`, `shape.set`, `key.add`, `value.set`, `layer.arrange` …) with
  arguments. `edit_document` applies a list of them, all or nothing.
- Copy a comp with everything in it with `comp.duplicate` (the copy lands right after it, named "<name> copy"), put comps in order with `comp.move` (`index` 0 = first), delete a throw-away comp with `comp.remove` (never the last one; Undo brings it back). A comp added without a name is numbered: "Scene 2", "Scene 3". Look and inspect tools called without `comp` read the **longest** comp and say so in their warnings; pass `comp` to choose.
- A **comp** has `width`, `height`, `fps`, `duration` (seconds), `background`, `shutter` (motion blur, degrees; 0 = off; see frame-parallax-motion-blur). A layer's `x`, `y` is where its **anchor** sits
  in its parent (comp px, 0,0 top-left; or the group's box). **Leave `x`, `y` out and it sits at its parent's centre.**
  The anchor by name: `anchor="top-left"`, `"top"`, `"left"`, `"center"` (the default), `"bottom-right"` … or a pair
  `anchor=(0, 1)`; as numbers `anchorX`/`anchorY`, 0 to 1 across the box.
  To turn round a known spot, `item.pivot(x, y)` puts the anchor on that comp point and nothing moves (any layer; the
  way for a drawing, whose canvas grows).
  A group's children are placed inside the group's own box (its top-left is 0,0).
- Colours are `#rrggbb` (or short, `#fff`). Mixing colours between keys happens in linear light.

## Keys and ease

A field is either **still** (it has a value) or **animated** (it has keys). Once a field has any key, **the keys alone decide**
its value and the layer's own value is ignored.

- A key is "this field has this value at this time". Between two keys the value travels; the **first key's `ease`** shapes
  the way to the next key. Before the first key and after the last, the value holds.
- One key never moves anything; you need two keys with different values.
- `ease` names: `linear`, `hold` (jumps at the next key), `smooth`, `snappy`, `natural`, `heavy`, `easeIn`, `easeOut`,
  `easeInOut`, `spring`, `bounce`, `custom` (x1 y1 x2 y2). See the guide `easing-and-overlap`.
- Which fields can be animated: every number and colour field, except the composition's own and a layer's `start`, `end`
  and `boxWidth`. `inspect_operations name: key.add` says which.

**`value.set` vs `key.add`.** `value.set` changes a field "as a person sees it now": on a still field it changes the value; on
an animated field it adds or changes the key at `at`. `key.add` always writes a key at time `t`. `key.clear` stops animating a
field and keeps its value at a time. When a person says "make the title bigger", use `value.set` (with `at` if animated).

## Running a script (`run_script`)

Write Python with the script functions (below). The script builds the whole document tree; the server **merges** it in.
Save the script as a file and pass its path, or pass the text itself:

```
run_script {"path": "C:/work/promo.py"}                       the file; its name (promo.py) is the script's name
run_script {"source": "comp(\"main\", ...)", "name": "promo.py"}   the text, under a name
```

Run it again after editing it and:

- what the script says changes; what you did not change stays;
- **your own earlier output updates**: a value, a key's new time, a layer you dropped. Only someone else's work holds
  a value back;
- **what a person moved by hand stays where they put it** (and what another agent or script changed), and the reply
  lists it as held back, naming the key and who changed it. Pass `force` with those keys (`"force": ["title.x"]`, or
  `true` for all) only when you really mean to overwrite their work;
- ids are what match old to new. Give your layers **explicit ids** (`text("title", ...)`) so a re-run finds the same layer.
  Left out, ids are counted per type (`text_1`, `text_2`) and skip any word quoted in the script.
- Keys have ids made from layer, field and time, so a key at the same time is the same key on re-run; a key you move to
  another time in the script is a new key in place of the old one (a person's retimed key keeps its id and stays).
- A script starts with `comp("id", ...)`: a layer line before it is refused ("make a composition first"). The scene arrives with its own frame; when the project already has a frame called `frame`, the new scene's is called `<scene id>-frame`. Ids the project already holds (a person's, another scene's) are never taken by a counted id.

**Replace or add depends on the script's `name`.** Run under the **same `name`**, a script replaces and merges what it made before (a person's edits stay). Run under a **new `name`**, it adds a second copy beside the first, and the reply warns that it did. To change something an earlier script made, run under that script's name. A second script can't make a scene an earlier script made (`comp("main")` again) or key its layers (`layer("dot0")`): the refusal names the script that made them; put the lines in that script. When a check fails because two scripts made the same things (for instance "drawings must be at different frames, in order"), the refusal names the earlier script: run under its name to replace them.

**Scripts cannot `import` anything but `math` and `random`, and cannot define classes.** `numpy`, `os` and the rest are refused. `math` and `random` are already there (`import math`, `import random` are fine), and so are these plain built-ins (and no others): `range`, `len`, `min`, `max`, `abs`, `round`, `sum`, `divmod`, `pow`, `enumerate`, `zip`, `map`, `filter`, `sorted`, `reversed`, `any`, `all`, `list`, `dict`, `tuple`, `set`, `frozenset`, `float`, `int`, `str`, `bool`, `isinstance`, `chr`, `ord`, and the errors `ValueError`, `KeyError`, `IndexError`, `TypeError`, `ZeroDivisionError`. There is no `print` (look at what the script made with `inspect_item`, `look_motion`, `look_frame`). `random` is **seeded**: it gives the same numbers on every run, so a re-run gives the same piece. `random.uniform(a, b)`, `random.randint(a, b)`, `random.choice(seq)`, `random.random()` use the script's own generator; `r = random(7)` makes another with its own seed (`r.uniform(...)`, `r.randint(...)`, `r.choice(...)`), handy to give each item in a loop its own: `random(100 + i)`. A `class` is refused ("classes aren't allowed in scripts; use functions and dicts"). A field can be keyed from your own Python: `item.sample("y", lambda t: …, start=, end=)` writes one key per frame (a list of values works too). For maths and data, scripts also have `plot_area`, `curve_points`, `line_d`, `nice_ticks`, `view3d`, `parse_table` and the rest (`data-math-and-graphs`); numpy work happens in your own Python, which hands the script its numbers.

```python
comp("main", width=1920, height=1080, fps=30, duration=4, background="#101014")
t = text("headline", body="Words", size=160)               # no x / y: the comp's centre
t.key("opacity", {0.0: 0, 0.6: 1}, ease="easeOut")          # {time: value} or {time: (value, ease)}
t.effect("shadow", dy=24, radius=60)
t.mask("reveal", w=0).key("w", {0.0: 0, 0.8: 1400})
with group("cluster", y=800) as cluster:                     # x left out: the centre across               # layers made inside go into the group
    shape("dot", shape="ellipse", w=24, h=24)
cluster.end = 4                                               # a field as an attribute is .set(end=4); t.x reads it back
```

Unknown fields, bad values, and animating something that cannot be animated fail loudly, naming the line and what to
write instead. A field written as an attribute (`t.end = 4`) goes through the same check as `.set(end=4)`: it is set or
refused, never dropped.

### What to write (the fields agents reach for)

| Layer | Its main fields |
|---|---|
| every layer | `x`, `y` (where its anchor sits, px; −20000 to 20000, so a tall parallax world or a long camera travel fits in that range: scale the world down or shorten the travel), `scale`, `scaleX`/`scaleY` (stretch one way; negative mirrors; key `scaleX` to squash), `rotation` (°), `opacity` **0–1**, `anchorX`/`anchorY` (0–1, default 0.5 = centre), `start`/`end` (s on screen), `blend`, `matte`, `timing` |
| `comp` | `width`, `height`, `fps`, `duration` (s), `background`, `shutter` (motion blur angle, 0 = off), `shutterSamples`, `workStart` / `workEnd` (the work area the screen shows on its ruler, s; 0 = none; export a part with `start` / `end`) |
| `shape` | `shape` = `rect` `ellipse` `triangle` `polygon` `star` `line` `arrow` `arc` `spiral`; `w`, `h`, `radius`; `fill`, `filled`; `stroke`, `strokeColor`, `strokeWidth` |
| `text` | `body` (the words), `size`, `weight`, `color`, `font` (`inspect_fonts` lists them), `italic`, `align` (`left` `center` `right`), `tracking` (em: 0.1 = a tenth of the letter size, −0.5 to 2), `letterDelay`, `letterOrder` |
| `path` | `d` (any SVG path data: M L H V C S Q T A Z, lower case relative; kept as absolute M L C Z, so reading it back shows those), `fill`, `filled`, `stroke`, `strokeColor`, `strokeWidth`, `trimStart`/`trimEnd` (0–1, draw on), `cap`, `dash` + `gap` (px; `dash=0` = solid; key `dashOffset` to march) |
| `drawing` | `w`, `h` (its canvas, px), `eachFrame`, `loop`, `drawnSoFar` (0–1: key 0 → 1 to paint its strokes on in the order they were painted) |
| `group` | `w`, `h`, `clip`, `layout` (auto layout), `background` + `bgColor` + `bgRadius` (a box behind its layers) |

Effects: `item.effect(type, id=None, **fields)`: the **type comes first**, the id is optional (counted for you,
like a layer's), and it **returns the effect**, which keys like a layer: `t.effect("blur", radius=30).key("radius",
{0.0: 30, 0.8: 0})` is a blur-in. Fields: `"blur"` (`radius`, px), `"shadow"` (`dx`, `dy`, `radius`, `color`, `strength`), `"glow"`, `"gradient"` (`color1`,
`color2`, `angle`: 90 = color1 left to color2 right, 180 = top to bottom; it arrives as the layer's **gradient fill**,
so `inspect_item` shows `fillType` and colour stops, not an effect, and a re-run keeps it that way), `"backdrop"` (frosted glass), `"grain"`, `"rough"` (edges wobble as if drawn by hand: `amount` px, `size` px of a bump, `detail`, `boil` frames), `"trail"`, `"smear"`. A mask: `item.mask(x=, y=, w=, h=)`.

The words you may know from CSS, SVG or other tools work too, and become the field above: `#fff` (= `#ffffff`),
`width`/`height` on a layer (= `w`/`h`), `text=` (= `body`), `fontSize`, `fontWeight`, `borderRadius`, `rotate`,
`steps` (= `timing`), `shape="circle"`, `ease="ease-out"`, `stroke="#fff"` (= stroke on in that colour), `fill="none"`
(= no fill; `filled=False`), `backgroundColor`. A colour never has transparency: use `opacity` or `fillOpacity`.

### Things that surprise people the first time

- **Keys are in the comp's seconds**, whatever the layer's `start` (`start` only hides it before then). Inside a group or
  layer timed from a marker (`marker="beat"`), times count from that marker. A key time may also name a marker
  (`"#beat"`, `"#beat-0.3"`).
- **Before its first key a field holds the first key's value.** A ripple keyed `{5.0: 0.5, 5.6: 0}` is half-visible from
  frame 0: start it with a key at 0 (`{4.9: 0, 5.0: 0.5, 5.6: 0}`) or give it `start=4.9`.
- **A spring settles at its last key and wobbles on the way:** with the default bounce it first reaches the target a
  fifth of the way through the stretch, overshoots most at about 30 %, and has settled by the last key. To land *on* a
  marker, put that first arrival there: `{"#beat-0.15": 0, "#beat+0.65": 1}` with `ease="spring"` (a 0.8 s stretch),
  then check with `look_motion` (overshoot) and `look_frame` at the marker.
- **Arrange things with boxes, not x / y sums:** `with column(padding=24, gap=16):`, `row`, `grid(columns=3)`,
  `stack` place and size what is made inside them, with `align`, `justify`, `grow=1`, sizes in px, `"50%"`, `"fill"`
  or `"fit"`, and texts that wrap where the box ends (guide `lay-out-a-screen`). Inside a box `x=` / `y=` fail unless
  `apart=True`. Keep raw `x`, `y` for motion and art: a moving shape, a painted world, a camera path.
- **Inside a group, `x`, `y` are in the group's box** (its top-left is 0, 0); a child with no `x`, `y` sits at the
  box's centre. A group made without `w`, `h` fits around what is inside when its `with` block ends. Given `x`, `y`
  (and no size), the group is a **point**: its children's `x`, `y` count from it (`with group("arm", x=520, y=650):` and
  a child at `x=0, y=80` sits 80 px below that point) and it turns and scales around it, so groups inside groups are
  joints (a shoulder, an elbow). Without `x`, `y`, its children keep the places written for them in its parent. To
  arrange several side by side or stacked, use a `column` / `row` / `stack` instead of sums.
- **Stacking order:** layers are drawn in the order they are made: the first one made is at the bottom, each later one
  on top of it (inside a group the same, among its children). Make the background first; `layer.arrange` with `index`
  (0 = bottom) moves one later.
- **A text's real width:** `w, h = title.measure()` in a script gives its box in its own px (before `scale`), measured
  by the code that draws it; place by it (`note.x = title.x + title.measure()[0] / 2 * title.scale + 24`). To measure
  words you have **not** made a layer for, `w, h = measure_text("SIGNAL", size=120, weight=700, font="…")` takes the same
  text fields and makes no layer, so nothing is left in the picture (never make a probe text just to measure it).
- **Text sits on its anchor too, and its anchor follows its alignment:** every text, made by a script, an operation
  or a person's Text tool, starts centred on `x`, `y` (anchor 0.5, `align="center"`). Without a `boxWidth`, changing
  `align` moves the across anchor with it, as After Effects' point text: `align="left"` makes `x` the left edge (anchor
  0), `"right"` the right edge (anchor 1), so a left-aligned column is just `align="left"` and its lines all start at
  `x`; changing the alignment later keeps `x` and the words re-flow around it. An anchor you set yourself (`anchorX`
  given with it, moved, keyed) is kept. `boxWidth` wraps the words into a box that wide, placed by its anchor like any
  box; there `align` only places each line inside the box, which stays put.
- **A rounded clip:** `clip=True` cuts to the group's rectangle. For rounded corners (a phone screen) give the group a
  mask with a radius: `screen.mask("round", x=0, y=0, w=390, h=844, radius=56)`.
- **`trimEnd` draws along the path in the order its points are written**, from the first point; on a closed path the
  closing segment (back to the start) comes last. To draw the other way round, write the points in the other order.
- **A path's points:** with no `x`, `y`, `w`, `h`, `d` is read as SVG reads it, in comp px (or the group's box): a line
  through (360, 600) passes through (360, 600). With any of them, `d` is in the path's own box (0, 0 = its top-left).
  A path is filled light grey by default; a line wants `fill="none"` (or `filled=False`) and a stroke.
- **Ids are one in the whole document**, effects' and masks' too: in a loop write `f"shadow{i}"`, or leave the id out.
- **A track matte** (`matte="logo_shape"`) must be a layer beside it (same group or comp); the matte layer itself is then
  only used as the matte.
- **Stepped timing** ("on twos / threes"): `timing="2"` (or `steps=2`) on the comp, a group or a layer (in the settings panel, **Animate on**; its first choice reads **Same as its group** inside a group and **Same as the scene** for a layer straight in a scene).

## Every script function

Everything a script can call, by job. The details and techniques are in the topic guides named.

### The scene and its layers

- `brief("the brief's own words")`: stores the brief's words on the document, for the person and for notes. It changes nothing in an export.
- `comp(id, width=, height=, fps=, duration=, background=)`: the scene. A script starts with it.
- `shape(id, **fields)`, `text(id, **fields)`, `image(id, **fields)`, `path(id, **fields)`, `group(id, **fields)`: the
  layers. Layers made inside `with group(...):` go in it, and their `x`, `y` are then in the group's box.
- `layer("id")` gives back an item made earlier in the script.
- Fields: `x`, `y` (the anchor, default the centre), `w`, `h`, `scale`, `rotation`, `opacity` 0–1. Shape:
  `shape="rect" | "ellipse" …`, `fill`, `radius`, `filled`, `stroke="#fff"`, `strokeWidth`. Text: `body`, `size`,
  `weight`, `color`, `align` (a text's `x` is its left edge, middle or right edge as `align` says). Path: `d` (SVG; with
  no `x`, `y`, `w`, `h` its points are comp px), `fill="none"`. Colours `"#rrggbb"` or `"#rgb"`.

### Keys, effects, masks, measuring

- `item.key(field, {time: value}, ease="easeOut")`: times in comp seconds or a marker (`"#beat-0.2"`). Before a field's
  first key it holds that key's value.
- `item.sample(field, lambda t: …, start=, end=)` keys a field from your own Python, one key per frame (or a list of
  values).
- `item.effect("shadow" | "glow" | "blur" | "gradient" | …, **fields)`; `item.mask(x=, y=, w=, h=)`.
- `item.pivot(x, y)`: the anchor on that comp point, nothing moves (a grown drawing's turning point).
- `w, h = t.measure()`: a text's real box in its own px (before scale), to place things by its width.
  `w, h = measure_text("words", size=64, font="…")` measures a text you have not made (no probe layer, nothing left in
  the picture).
- `scramble(id, body, start=, end=)` cycles characters into words (guide `type-and-kinetic-text`).
- `counter(id, start, to, at=, duration=, decimals=, prefix=)` is one text that counts (never stack texts).

### Time by name

- `marker("reveal", 3)` makes a shared project marker and gives `"#reveal"`, which adds like a number
  (`text(start=r + 0.5, end="#out")`, `tap(at=)`, `scramble(start=)`). Any time may name a marker. A marker may be
  placed from another (`marker("title", "#data+11")`); a name may not end in `+number` / `-number`, and one name is one
  marker per script.
- `after(item, gap=0)`: when its last key lands (its start when it has none), plus `gap` s; a marker time when that key
  or the item is on a marker.
- `stagger(items, every=0.1, start=0)` gives `[(time, item), …]`, the first at `start`, each next `every` s later.
- `beats()` gives the scene's music beats in seconds (the music is made in RostrumSound); `beats(bpm=120, start=,
  count=)` a grid without a song (`end=` too: default the scene's length). Guide `timing-to-music`.

### Layout (guide `lay-out-a-screen`)

- `with row / column / grid / stack(padding=, gap=, align=, justify=, w=px | "50%" | "fill" | "fit",
  tw="flex-col gap-4 p-6"):` layers made inside are placed and sized for you (`grow=`, `span=`; `x` / `y` only with
  `apart=True`).
- `anchor="top-left" | "left" | "center" | …` names any layer's pivot, and a layer with no `x` / `y` sits at its
  parent's centre.

### The frame (what is exported; guide `frame-parallax-motion-blur`)

`f = frame()`; `f.key("x", {0: 960, 4: 2600})`; `f.fit(["hills", "tree"], at=4)` frames layers as they show then
(depth counted); `f.fit(rect=(x, y, w, h), at=4, ease="easeInOut")` (ease: how it moves into that framing; a fit where
it already is changes nothing); `f.cut(at=6, to="rect", rect=(3200, 0, 1920, 1080))` or `f.cut(at="#logo lands")`
jumps it; `f.home(at=8)`. The same as the operations `frame.fit`, `frame.cut`, `frame.home` (target `"frame"`).

### Drawings (guide `drawing-and-frame-by-frame`)

`d = drawing(id, w=, h=, eachFrame=True)`; `f = d.frame(at)`; `f.paint()`; `p.stroke(points, **brush)`;
`p.letters(text, x=, y=, height=, font="script", **brush)` paints hand-lettered words as brush strokes in writing order
(write on with `drawnSoFar`). Every drawing's paint joins the layer's one set of paint layers.

### Equations, graphs and charts (guide `data-math-and-graphs`)

`plot_area`, `curve_points`, `param_points`, `polar_points`, `line_d`, `lines_d`, `nice_ticks`, `tick_label`,
`view3d`, `surface_lines`, `parse_table`; `math_text(id, r"\frac{a}{b}", x=, y=, size=, color=)`: a typeset equation as
a group of path layers, one per symbol.

### Characters (guide `character-rigging-and-lip-sync`)

- `limb(id, x=, y=, lengths=, widths=, kind="arm" | "leg", parent=, color=)` makes a bending arm or leg (bones, IK,
  parts in the body's colour unless `color=` is given). Without `widths=` it is sized to the body: the upper part 0.26 ×
  its width, a leg 0.3 ×. A mitten hand with a thumb; `hand="ball"` a circle. An arm rests with its elbow bent 35°
  (`relax=`) and, keyed on `arm.upper` alone, its forearm bends and trails by itself; `arm.out` is the rotation sign
  that swings it away from the body. It tapers from `widths[0]` at the shoulder to a thinner wrist (`taper=0.2`), has a
  `joint="round" | "ball" | "none"` at the elbow / knee and a darker `outline=` so a bent arm reads in a small still,
  even across the body. Make legs with `limb(kind="leg")` so they can act.
- `pose({limb or bone: turn}, at=)` hits a key pose with anticipation and overshoot (`pose({hip: {"moveY": 40}})`
  crouches: IK feet stay planted, knees bend).
- `step(legs=[a, b], by=px, at=)` steps to a new spot foot by foot.
- `walk(legs=[a, b], arms=, body=, start=, end=, step=, stride=)`, `idle(chest, head=, arms=, legs=)` (legs: weight
  shifts foot to foot), `follow(bone)`, `blink(eyes, open=, closed=)` write plain keys.

### Screens (guide `ui-and-product-animation`)

- `device(id, kind="phone" | "laptop" | "browser", fit=share of the picture's height, anchor=, screen=colour)` sizes and
  centres itself and returns its screen, a column. Left out, `kind` is the device the id names (`device("laptop")` draws
  a laptop), else a phone; a device it can't draw (a tablet) or an id naming another kind than `kind=` is refused.
- `status_bar`, `nav_bar`, `tab_bar`, `list_rows`, `card`, `button`, `toggle`, `bars`, `chart` made in it (or any container) go
  one under the other, full width; `lower_third` hugs its words (top level: the lower-left title-safe area; guide
  `lower-thirds-and-charts`).
- `pointer()` and `tap(pointer, target, at=, then=)` land the tip on the target's centre (following it if it moves) and react (guide `tap-and-react`).

### What a script may use

No `import` except `math` and `random` (seeded: the same numbers every run; `random(7)` is your own seeded generator
with `.uniform` / `.randint` / `.choice` / `.random`) and no classes: use functions and dicts. An error names the line
and what to write instead.

## Reading errors

A failed call says `ok: false` and the one line `Error: <where>: <subject> <what is wrong>. Accepted: … <hint>`. Read **Accepted**:
it lists what would have worked; a wrong argument name also says which one you meant (`from` → "Did you mean start?").
Edits are all or nothing, so nothing changed.
