# Start here: Rostrum2D

Rostrum2D makes motion graphics: type, shapes, images, UI animation. You and a person edit **the same document**, so
whatever you build stays editable by hand, and whatever they move stays moved.

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
  lists them; with an `id` it shows one part's values and the operations that fit it right now.
- `inspect_operations` lists everything you can do (`text.set`, `shape.set`, `key.add`, `value.set`, `layer.arrange` …) with
  arguments. `edit_document` applies a list of them, all or nothing.
- Delete a throw-away comp with `comp.remove` (never the last one). Look and inspect tools called without `comp` read the **longest** comp and say so in their warnings; pass `comp` to choose.
- A **comp** has `width`, `height`, `fps`, `duration` (seconds), `background`. A layer's `x`, `y` is where its **anchor** sits
  in the comp, in pixels (0,0 is top-left). The anchor is `anchorX`/`anchorY`, 0 to 1 across the box, default 0.5 = centre.
  A group's children are placed inside the group's own box (its top-left is 0,0).
- Colours are `#rrggbb` (or short, `#fff`). Mixing colours between keys happens in linear light.

## The one animation model: keys + ease

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

## Timing to the story: layers timed from a marker

Cuts, entrances and beats that other apps also use (the music's drop, the 3D product landing) go on the project's
**shared markers** (`inspect_markers`, `edit_markers`), never copied as numbers. Give a layer or a whole group
**Timed from marker** (`marker="reveal"`): its *Starts at*, *Ends at* and keys, and everything inside it, count
from that marker. Move the marker in any app and the shot moves with it; Sound's music follows the same marker.

```python
with group("reveal_shot", marker="reveal", end=4.0):     # visible from the marker for 4 s
    t = text("name", body="Lull", size=180)
    t.key("opacity", {0.0: 0, 0.4: 1})                     # 0.0 = the moment of the marker
```

- A layer inside a timed group with its own `marker` counts from its own marker.
- **Ends at marker** (`endMarker="reveal"`) ends a layer on another marker: the phone shot is gone exactly when the
  reveal starts, wherever either marker moves.
- **Cuts:** the frame jumps on a key timed on a marker: `frame().cut(at="#reveal", to="rect", rect=(2240, 0, 1920, 1080))`
  (or `frame.cut` with `at: "#reveal"`), so the cut moves with the marker (see `frame-parallax-motion-blur`).
- **Lead-ins:** *Starts at* may be below 0, counted back from the marker (`start=-0.2` appears 0.2 s before it).
  A group's lead-in shows its children too: a child left at *Starts at* 0 starts with its group; a child with a
  start of its own counts it from the marker (`start=0.2` appears 0.2 s after it).
- **A key on its own marker:** a key's time may name a marker, as Sound's times do: `t.key("opacity", {0.0: 0,
  "#drop-0.1": 0.2, "#drop+0.2": 1})` (or `key.add` with `"t": "#drop+0.2"`). It lands at that moment of the
  project, whatever its layer counts from, so one layer can hit "drop" and "logo lands" both, and a key may sit
  before the layer's start (a pre-roll: the move is under way when the layer appears). Moving the marker moves the
  key; a marker that is gone stops the render naming the key. `look_motion` (`what: "curve"`), the curve editor and the settings panel
  show the marker ("drop +0.2 s"); dragging such a key keeps it on its marker with a new offset.
- Drawings' frames, effects', masks' and a rig's keys move with their layer.
- `look_motion`, `look_frame` and the export all read the times as they play (marker + time). `inspect_item`
  shows the times as written, from the marker.
- A marker the project doesn't have stops the render with a message, and `inspect_diagnose` lists it.

## Scripts (`run_script`)

Write Python with the script API (below). The script builds the whole document tree; the server **merges** it in. Run it
again after editing it and:

- what the script says changes; what you did not change stays;
- **what a person moved by hand stays where they put it**, and the reply lists it as held back with a warning. Pass `force`
  (a list of the held keys, or `true`) only when you really mean to overwrite their work;
- ids are what match old to new. Give your layers **explicit ids** (`text("title", ...)`) so a re-run finds the same layer.
  Left out, ids are counted per type (`text_1`, `text_2`) and skip any word quoted in the script.
- Keys have ids made from layer, field and time, so a key at the same time is the same key on re-run.
- A script starts with `comp("id", ...)`: a layer line before it is refused ("make a composition first"). The scene arrives with its own frame; when the project already has a frame called `frame`, the new scene's is called `<scene id>-frame`. Ids the project already holds (a person's, another scene's) are never taken by a counted id.

**Replace or add depends on the script's `name`.** Run under the **same `name`**, a script replaces and merges what it made before (a person's edits stay). Run under a **new `name`**, it adds a second copy beside the first, and the reply warns that it did. To change something an earlier script made, run under that script's name. When a check fails because two scripts made the same things (for instance "drawings must be at different frames, in order"), the refusal names the earlier script: run under its name to replace them.

**Scripts cannot `import` anything but `math` and `random`, and cannot define classes.** `numpy`, `os` and the rest are refused. `math` and `random` are already there (`import math`, `import random` are fine), and so are Python's plain built-ins: `range`, `len`, `min`, `max`, `abs`, `round`, `enumerate`, `zip`, `sorted`, `sum`. `random` is **seeded**: it gives the same numbers on every run, so a re-run gives the same piece. `random.uniform(a, b)`, `random.randint(a, b)`, `random.choice(seq)`, `random.random()` use the script's own generator; `r = random(7)` makes another with its own seed (`r.uniform(...)`, `r.randint(...)`, `r.choice(...)`), handy to give each item in a loop its own: `random(100 + i)`. A `class` is refused ("classes aren't allowed in scripts; use functions and dicts").

```python
comp("main", width=1920, height=1080, fps=30, duration=4, background="#101014")
t = text("headline", body="Words", size=160, x=960, y=520)
t.key("opacity", {0.0: 0, 0.6: 1}, ease="easeOut")          # {time: value} or {time: (value, ease)}
t.effect("shadow", dy=24, radius=60)
t.mask("reveal", w=0).key("w", {0.0: 0, 0.8: 1400})
with group("cluster", x=960, y=800):                          # layers made inside go into the group
    shape("dot", shape="ellipse", w=24, h=24)
```

Unknown fields, bad values, and animating something that cannot be animated fail loudly, naming the line and what to
write instead.

### What to write (the fields agents reach for)

| Layer | Its main fields |
|---|---|
| every layer | `x`, `y` (where its anchor sits, px), `scale`, `rotation` (°), `opacity` **0–1**, `anchorX`/`anchorY` (0–1, default 0.5 = centre), `start`/`end` (s on screen), `blend`, `matte`, `timing` |
| `comp` | `width`, `height`, `fps`, `duration` (s), `background` |
| `shape` | `shape` = `rect` `ellipse` `triangle` `polygon` `star` `line` `arrow` `arc` `spiral`; `w`, `h`, `radius`; `fill`, `filled`; `stroke`, `strokeColor`, `strokeWidth` |
| `text` | `body` (the words), `size`, `weight`, `color`, `font` (`inspect_fonts` lists them), `italic`, `align` (`left` `center` `right`), `tracking` (em: 0.1 = a tenth of the letter size, −0.5 to 2), `letterDelay`, `letterOrder` |
| `path` | `d` (SVG data: M L C Z), `fill`, `filled`, `stroke`, `strokeColor`, `strokeWidth`, `trimStart`/`trimEnd` (0–1, draw on), `cap`, `dash` |
| `group` | `w`, `h`, `clip`, `layout` (auto layout), `background` + `bgColor` + `bgRadius` (a box behind its layers) |

Effects: `item.effect("shadow", dx=, dy=, radius=, color=, strength=)`, `"glow"`, `"blur"`, `"gradient"` (`color1`,
`color2`, `angle`: 90 = color1 left to color2 right, 180 = top to bottom), `"backdrop"` (frosted glass), `"grain"`, `"trail"`, `"smear"`. A mask: `item.mask(x=, y=, w=, h=)`.

The words you may know from CSS, SVG or other tools work too, and become the field above: `#fff` (= `#ffffff`),
`width`/`height` on a layer (= `w`/`h`), `text=` (= `body`), `fontSize`, `fontWeight`, `borderRadius`, `rotate`,
`steps` (= `timing`), `shape="circle"`, `ease="ease-out"`, `stroke="#fff"` (= stroke on in that colour), `fill="none"`
(= no fill; `filled=False`), `backgroundColor`. A colour never has transparency: use `opacity` or `fillOpacity`.

Things that surprise people the first time:

- **Keys are in the comp's seconds**, whatever the layer's `start` (`start` only hides it before then). Inside a group or
  layer timed from a marker (`marker="beat"`), times count from that marker. A key time may also name a marker
  (`"#beat"`, `"#beat-0.3"`).
- **Before its first key a field holds the first key's value.** A ripple keyed `{5.0: 0.5, 5.6: 0}` is half-visible from
  frame 0: start it with a key at 0 (`{4.9: 0, 5.0: 0.5, 5.6: 0}`) or give it `start=4.9`.
- **A spring settles at its last key and wobbles on the way:** with the default bounce it first reaches the target a
  fifth of the way through the stretch, overshoots most at about 30 %, and has settled by the last key. To land *on* a
  marker, put that first arrival there: `{"#beat-0.15": 0, "#beat+0.65": 1}` with `ease="spring"` (a 0.8 s stretch),
  then check with `look_motion` (overshoot) and `look_frame` at the marker.
- **Inside a group, `x`, `y` are in the group's box** (its top-left is 0, 0). Give the group `w`, `h` and place the
  children in it (`w / 2`, `h / 2` is its middle); a group made without a size is fitted to what is inside it when the
  `with` block ends, and its layers keep their place on screen.
- **A path's points:** with no `x`, `y`, `w`, `h`, `d` is read as SVG reads it, in comp px (or the group's box): a line
  through (360, 600) passes through (360, 600). With any of them, `d` is in the path's own box (0, 0 = its top-left).
  A path is filled light grey by default; a line wants `fill="none"` (or `filled=False`) and a stroke.
- **Ids are one in the whole document**, effects' and masks' too: in a loop write `f"shadow{i}"`, or leave the id out.
- **A track matte** (`matte="logo_shape"`) must be a layer beside it (same group or comp); the matte layer itself is then
  only used as the matte.
- **Stepped timing** ("on twos / threes"): `timing="2"` (or `steps=2`) on the comp, a group or a layer (in the settings panel, **Animate on**; its first choice reads **Same as its group** inside a group and **Same as the scene** for a layer straight in a scene).

## Seeing your work (do it every time)

You can't judge motion from the script. Look.

| Tool | Use it to |
|---|---|
| `look_motion` | Read **what moves and when** from the keys, no rendering: each layer's moves, path, peak speed, ease, overshoot, holds; entrances that overlap; where nothing moves; layers off screen at the end; keys that do nothing. Facts only. Short by default (a line a layer); pass `full` (with `layers`) for every move. Run it after every script. |
| `look_frame` (`what: "sheet"`) | See the **whole motion at a glance**: N frames over a time range in one labelled image. |
| `look_frame` | See **one moment** in detail, at a time or frame number. Look at the landing frames and the hold frames. |
| `look_at` | Ask **what is at a point** (x, y, time; `space` frame or world): layers covering it, top first, with values (boxes are approximate). |
| `look_frame` (`what: "world"`) | See the **whole canvas** with the frame and its path drawn on it (a dot per frame, keys, cuts), and a ruler of world px. |
| `look_frame` (`what: "in_frame"`) | Ask **what is in the frame** at a time, or over a span: each layer in, partly in or out, and when it enters and leaves. |
| `render_video` | Export an mp4. Always a job: `inspect_job` with `wait_s` to follow it. |

Look pictures go to the project's `looks` folder (`<project folder>\looks\`; with no project open, to Rostrum's look cache); every reply gives the full path in `files`. `look_frame` and `look_frame` (`what: "sheet"`) use the
same engine as export, so what you see is what the file will be.

## Reading errors

A failed call says `ok: false` and the one line `Error: <where>: <subject> <what is wrong>. Accepted: … <hint>`. Read **Accepted**:
it lists what would have worked. Edits are all or nothing, so nothing changed.

## The guides (one line each: when to read it)

| Guide | Read it when |
|---|---|
| `type-and-kinetic-text` | you set type: fonts, variable axes, OpenType features, per-letter animation, gradient letters, building a title in steps |
| `ui-and-product-animation` | you build screens and product shots: boxes, masks, frosted glass, shadows, tilt and depth |
| `colour-and-blending` | you mix layers with blend modes (screen, multiply, overlay …) or grade a layer: exposure, levels, curves, a .cube LUT |
| `shape-and-path-animation` | you draw with the pen, combine shapes, draw a stroke on, dash it |
| `drawing-and-frame-by-frame` | you paint brush strokes and draw one picture per frame |
| `painted-backgrounds` | you paint a big background in depth layers (far / mid / near) for the frame's moves and parallax |
| `3d-renders-in-2d` | you place a Rostrum3D item's render (product shot) in a comp, following new renders |
| `character-rigging-and-lip-sync` | you make a figure move from bones and IK, or make a mouth follow a voice |
| `frame-parallax-motion-blur` | you move the frame, look through it, pin a title to it, set depth between layers, motion blur, smears, trails |
| `import-and-export` | you bring in SVG, PDF, PSD, Figma, or hand over MP4, WebM, GIF, ProRes 4444, PNG sequence, Lottie |
| `easing-and-overlap` | you choose how a move travels (ease curves) and check that moves overlap as you meant |
| `text-on-a-path`, `curve-editor`, `expressions` | text follows a curve; you shape the easing by hand; you drive a value from a formula |

Each guide says what exists today, with the tool, operation or field name. Where something is planned but missing, it says
"not yet".
