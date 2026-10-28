# Start here: Rostrum2D

Rostrum2D makes motion graphics: type, shapes, images, UI animation. You and a person edit **the same document**, so
whatever you build stays editable by hand, and whatever they move stays moved.

**Your time.** Every reply ends with a clock line (time since your first call, and the minutes left when you were given a
budget). A first version usually takes a fraction of the time: the rest is for looking at it (sheets of the whole span, the
export, single frames, zooms) and refining what you see, in passes. `inspect_project` with `what: "session"` lists what is
still unchecked. More in [Using your time](#using-your-time).

## Open or make a project

The server starts on the person's last project. To work somewhere else, or to start a new piece:

- `run_open_project {"folder": "C:/Users/me/Videos/launch"}`: the folder is an absolute path. If it doesn't exist yet it
  is made (with any folders above it), with an empty document `main` in it; an existing project opens as it is.
- `item` names the document: `{"folder": "...", "item": "teaser"}` opens `teaser`, or starts it empty beside the others.
- `run_open_project {"what": "recent"}` lists the person's recent projects.
- A refused call (a path that isn't absolute, a file instead of a folder, a document name with spaces) makes nothing.

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
  in the comp, in pixels (0,0 is top-left). The anchor is `anchorX`/`anchorY`, 0 to 1 across the box, default 0.5 = centre.
  To turn round a known spot, `item.pivot(x, y)` puts the anchor on that comp point and nothing moves (any layer; the
  way for a drawing, whose canvas grows).
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

- Inside a timed group, `start`, `end` and key times are **seconds from the marker**: `end=4.0` is 4 s after it, not
  at 4 s of the comp.
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
- Move a marker with `edit_markers` and `marker.move`; its target may be the marker's name or its id:
  `{"op": "marker.move", "target": ["drop"], "args": {"at": 5.5}}`.

## Scripts (`run_script`)

Write Python with the script API (below). The script builds the whole document tree; the server **merges** it in.
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

**Replace or add depends on the script's `name`.** Run under the **same `name`**, a script replaces and merges what it made before (a person's edits stay). Run under a **new `name`**, it adds a second copy beside the first, and the reply warns that it did. To change something an earlier script made, run under that script's name. When a check fails because two scripts made the same things (for instance "drawings must be at different frames, in order"), the refusal names the earlier script: run under its name to replace them.

**Scripts cannot `import` anything but `math` and `random`, and cannot define classes.** `numpy`, `os` and the rest are refused. `math` and `random` are already there (`import math`, `import random` are fine), and so are these plain built-ins (and no others): `range`, `len`, `min`, `max`, `abs`, `round`, `sum`, `divmod`, `pow`, `enumerate`, `zip`, `map`, `filter`, `sorted`, `reversed`, `any`, `all`, `list`, `dict`, `tuple`, `set`, `frozenset`, `float`, `int`, `str`, `bool`, `isinstance`, `chr`, `ord`, and the errors `ValueError`, `KeyError`, `IndexError`, `TypeError`, `ZeroDivisionError`. There is no `print` (look at what the script made with `inspect_item`, `look_motion`, `look_frame`). `random` is **seeded**: it gives the same numbers on every run, so a re-run gives the same piece. `random.uniform(a, b)`, `random.randint(a, b)`, `random.choice(seq)`, `random.random()` use the script's own generator; `r = random(7)` makes another with its own seed (`r.uniform(...)`, `r.randint(...)`, `r.choice(...)`), handy to give each item in a loop its own: `random(100 + i)`. A `class` is refused ("classes aren't allowed in scripts; use functions and dicts"). For maths and data, scripts also have `plot_area`, `curve_points`, `line_d`, `nice_ticks`, `view3d`, `parse_table` and the rest (`data-math-and-graphs`); numpy work happens in your own Python, which hands the script its numbers.

```python
comp("main", width=1920, height=1080, fps=30, duration=4, background="#101014")
t = text("headline", body="Words", size=160, x=960, y=520)
t.key("opacity", {0.0: 0, 0.6: 1}, ease="easeOut")          # {time: value} or {time: (value, ease)}
t.effect("shadow", dy=24, radius=60)
t.mask("reveal", w=0).key("w", {0.0: 0, 0.8: 1400})
with group("cluster", x=960, y=800) as cluster:               # layers made inside go into the group
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
- **A group made without `w`, `h` is as big as the comp while you fill it.** Leave its `x`, `y` out and its children
  are placed in comp px. Give it `x=300, y=300` and that comp-sized box is *centred* there (anchor 0.5), so a child at
  (100, 100) lands far up and left, off screen. To place a group by a point, give it `w`, `h` (then `x`, `y` is its
  centre, and its children sit in its box), or `anchorX=0, anchorY=0` as well (then `x`, `y` is its top-left).
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

## Seeing your work (do it every time)

You can't judge motion from the script. Look.

| Tool | Use it to |
|---|---|
| `look_motion` | Read **what moves and when** from the keys, no rendering: each layer's moves, path, peak speed, ease, overshoot, holds; entrances that overlap; where nothing moves; layers off screen at the end; keys that do nothing. Facts only. On screen means the engine draws it into the picture (groups, frame / camera, depth, tilt, drawing cycles counted). Short by default: a line a moving layer; identical findings (a hundred windows entering together) one line with a count and examples, the ones that matter first (never on screen, not on screen at the end, keys after the end, keys that do nothing, quiet stretches, overlapping entrances); at most 20 layers and 20 finding lines, then how many more; pass `layers` for just those, `limit` for more, `all` for no cap, `full` (with `layers`) for every move. Run it after every script. |
| `look_frame` (`what: "sheet"`) | See the **whole motion at a glance**: `count` frames (2–24) from `start` to `end` (seconds) in one labelled image `width` px wide (default 1600, the whole sheet: ~390 px tiles 4 across), `cols` tiles a row. For moments you pick (not evenly spaced) give `look_frame` `times: [0.5, 1.2, 3.0]`: the same sheet. For detail, one `look_frame`. With `video: "<mp4 path>"` (with `sheet`, or `times`) the sheet is made of a **finished mp4's own frames**: the export itself, no item needed. |
| `look_frame` | See **one moment** in detail, at a time or frame number. Look at the landing frames and the hold frames. `area: [x, y, w, h]` (comp px) draws only that part, sharp at `width` (a zoom on a mouth or an edge); `times` + `cols` for a sheet of chosen moments. |
| `look_at` | Ask **what is at a point** (x, y, time; `space` frame or world): layers covering it, top first, with values (boxes are approximate). |
| `look_frame` (`what: "world"`) | See the **whole canvas** with the frame and its path drawn on it (a dot per frame, keys, cuts), and a ruler of world px. |
| `look_frame` (`what: "in_frame"`) | Ask **what is in the frame** at a time, or over a span: each layer in, partly in or out, and when it enters and leaves. |
| `look_frame` (`what: "empty"`) | Find **blank, pale and standing-still stretches** from tiny pictures every 0.5 s (seconds to run), with times and numbers: near-empty frames (almost only background), washed-out frames (all pale, low contrast), nothing moving for `min_still` s (default 2), and whether the piece ends on one. Facts, not verdicts: a held title is yours to judge. `video: "<mp4 path>"` checks a finished file. |
| `look_review` | List the film's **weakest moments, ranked**, each a located fault with times: a near-empty stretch, a text cut off by the frame edge, an old heading still faintly behind a new one, a set of parts (a chart's bars, a list's rows) not drawn in yet while the rest of its group shows, a plain card opening empty, a character's pose barely changing for 6 s or more, framing held 10 s or more (no camera move or cut), nothing moving, a subject cut by the edge. `beats: [{"at": 25, "to": 30, "expect": "camera move"}]` (also `cut`, `pose change`, `<layer id> moves`, `<layer id> shows`) names a beat of the brief that never happens. Seconds to run on a 30 s film; `video` reads an exported mp4's pictures. Facts, not taste: a held title may be meant. |
| `render_video` | Export an mp4. Always a job: `inspect_job` with `wait_s` to follow it. The finished reply names the one deliverable (`video`: your `path` copy, else the project render) and says whether it has sound (`has_sound`). It also checks the finished file (blank, washed-out or unchanged stretches: `quiet_stretches`; subjects cut by the edge: `edge_cuts`) and ends with the time left and the weakest moments from `look_review`. |

**The loop: make → export → review → fix.** Every finished export's reply ends with the time left and its top weakest
moments (from `look_review`), e.g. *Time left: 11 min. Weakest moments, most visible first: 1. 22–23 s: near-empty …
2. 12 s: text "headline" is cut off by the right edge …* Fix the top one, export again, and repeat while time is left:
each pass is a few minutes. Also look at a sheet of the finished piece (`look_frame` `what: "sheet"` with `video` = the
mp4's path, after your last edit): `look_review` names what can be measured, your eyes judge the rest. A sheet from
before your last edit doesn't count.

### Using your time

Every reply ends with a clock line, e.g. *Session 6 min 12 s of real time since your first call (your thinking included) · 23 calls · last look at
the picture 4 edits ago*. The session starts at your first call; if `ROSTRUM_SESSION_BUDGET_MIN` is set it also says how many
minutes are left. After an export it also names the kinds of look not done yet (a full-size single frame, the motion with
`look_motion`). The clock is the only time you have: a long stretch without a reply is not time used up, and the time
you were given is for making **and looking**.

`inspect_project` with `what: "session"` says what is still unchecked: edits since you last looked at the picture, times
of the piece you have never looked at (a look at a time covers 2 s either side of it, a sheet covers each of its tiles),
whether the export was looked at, and the stretches the last empty check named. A technique for the time you have:

- Work in **passes**, not one long build: structure and timing first, then look at sheets of the whole span, then refine what the
  sheets show (a moment looks different at 100 % in one frame than in a tile, so also look at single frames and `area` zooms).
- Use the time to look: a sheet of the whole span after each pass, a sheet of the **export** after each render, a zoom on
  anything small. A piece you have not looked at is not finished, however long the script is.
- Stop when the checks say nothing is unchecked **and** the picture at every time looks as you mean it, not when a count of
  calls or minutes feels enough.

Look pictures go to the project's `looks` folder (`<project folder>\looks\`; with no project open, to Rostrum's look cache); every reply gives the full path in `files`. `look_frame` and `look_frame` (`what: "sheet"`) use the
same engine as export, so what you see is what the file will be.

## Music and sound

Sound is made in **RostrumSound**, never in 2D: its own MCP server (`rostrum-sound`) opened on the **same project
folder** (its `run_open_project`). Read its guides `start-here` and `scoring-motion` there. What it makes plays here
with the picture and goes under an mp4 export (`render_video`, `sound`, on by default when the project has sound).
Tie the two by **shared markers** ("drop", "logo lands"; `inspect_markers`), never copied times. From 2D:

- `inspect_sounds` lists what you can tie to a layer: a note or hit on the song's own instruments, the person's
  recordings, RostrumSound's library; `edit_sound_cue {layer, sound}` ties one to the layer's start (Sound mixes it).
- `render_export` `format: "motion"` hands your layers' motion to RostrumSound (`edit_sounds_from_motion` there
  suggests notes and hits for each landing).
- **No sound?** A render of a project with no RostrumSound item, or with `sound: false`, makes a silent mp4; it never fails for that. The Sound server is only needed to make or change the music, not to render it.
- Guide `timing-to-music`: hearing the song, its beats, snapping and tying layers to its markers.

## Reading errors

A failed call says `ok: false` and the one line `Error: <where>: <subject> <what is wrong>. Accepted: … <hint>`. Read **Accepted**:
it lists what would have worked; a wrong argument name also says which one you meant (`from` → "Did you mean start?").
Edits are all or nothing, so nothing changed.

## The guides (one line each: when to read it)

| Guide | Read it when |
|---|---|
| `type-and-kinetic-text` | you set type: fonts, variable axes, OpenType features, per-letter animation, gradient letters, building a title in steps |
| `ui-and-product-animation` | you build screens and product shots: devices and screen blocks in one call (`device`, `list_rows`, `card`, `bars` …), counting numbers (`counter`), boxes, masks, frosted glass, shadows, tilt and depth |
| `colour-and-blending` | you mix layers with blend modes (screen, multiply, overlay …) or grade a layer: exposure, levels, curves, a .cube LUT |
| `shape-and-path-animation` | you draw with the pen, combine shapes, draw a stroke on, dash it |
| `drawing-and-frame-by-frame` | you paint brush strokes and draw one picture per frame |
| `painted-backgrounds` | you paint a big background in depth layers (far / mid / near) for the frame's moves and parallax, or hand-letter a title as brush strokes |
| `3d-renders-in-2d` | you place a Rostrum3D item's render (product shot) in a comp, following new renders |
| `character-rigging-and-lip-sync` | you make a figure move from bones and IK (`limb`, `walk`, `idle`, `follow`, `blink`, `layer(id)` in a script), or make a mouth follow a voice |
| `frame-parallax-motion-blur` | you move the frame, look through it, pin a title to it, set depth between layers, motion blur, smears, trails |
| `import-and-export` | you bring in SVG, PDF, PSD, Figma, or hand over MP4, WebM, GIF, ProRes 4444, PNG sequence, Lottie |
| `easing-and-overlap` | you choose how a move travels (ease curves) and check that moves overlap as you meant |
| `text-on-a-path`, `curve-editor`, `expressions` | text follows a curve; you shape the easing by hand; you drive a value from a formula |
| `data-math-and-graphs` | you plot an equation or a function, draw axes and ticks, a 3D-looking surface, a chart from a table, or one design filled in from many rows |

`inspect_guide {"topic": ...}` gives a long guide's first sections and the headings of the rest; ask for one with
`section` (words of its heading) or `"section": "all"`. Each guide says what exists today, with the tool, operation or field name. Where something is planned but missing, it says
"not yet".
