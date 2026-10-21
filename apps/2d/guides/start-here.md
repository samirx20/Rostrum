# Start here: Rostrum2D

Rostrum2D makes motion graphics: type, shapes, images, UI animation. You and a person edit **the same document**, so
whatever you build stays editable by hand, and whatever they move stays moved.

## The document

```
document ─ comps ─ comp ─ layers ─ shape | text | image | group (a group holds layers)
                          each layer ─ effects (blur, glow, gradient, shadow)
                                     ─ masks (the part that shows)
                                     ─ keys  (the animation)
```

- Every part has an **id** (`title`, `bg`, `title.opacity.k200`). Use ids, never names or positions. `inspect_item` with no `id`
  lists them; with an `id` it shows one part's values and the operations that fit it right now.
- `inspect_operations` lists everything you can do (`text.set`, `shape.set`, `key.add`, `value.set`, `layer.arrange` …) with
  arguments. `edit_document` applies a list of them, all or nothing.
- A **comp** has `width`, `height`, `fps`, `duration` (seconds), `background`. A layer's `x`, `y` is where its **anchor** sits
  in the comp, in pixels (0,0 is top-left). The anchor is `anchorX`/`anchorY`, 0 to 1 across the box, default 0.5 = centre.
  A group's children are placed inside the group's own box (its top-left is 0,0).
- Colours are `#rrggbb`. Mixing colours between keys happens in linear light.

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

```python
comp("main", width=1920, height=1080, fps=30, duration=4, background="#101014")
t = text("headline", body="Words", size=160, x=960, y=520)
t.key("opacity", {0.0: 0, 0.6: 1}, ease="easeOut")          # {time: value} or {time: (value, ease)}
t.effect("shadow", dy=24, radius=60)
t.mask("reveal", w=0).key("w", {0.0: 0, 0.8: 1400})
with group("cluster", x=960, y=800):                          # layers made inside go into the group
    shape("dot", shape="ellipse", w=24, h=24)
```

Unknown fields, bad values, and animating something that cannot be animated fail loudly, naming the line and what is accepted.

## Seeing your work (do it every time)

You can't judge motion from the script. Look.

| Tool | Use it to |
|---|---|
| `look_motion` | Read **what moves and when** from the keys, no rendering: each layer's moves, path, peak speed, ease, overshoot, holds; entrances that overlap; where nothing moves; layers off screen at the end; keys that do nothing. Facts only. Run it after every script. |
| `look_sheet` | See the **whole motion at a glance**: N frames over a time range in one labelled image. |
| `look_frame` | See **one moment** in detail, at a time or frame number. Look at the landing frames and the hold frames. |
| `look_at` | Ask **what is at a point** (x, y, time): layers covering it, top first, with values (boxes are approximate). |
| `render_video` | Export an mp4. Always a job: `inspect_job` with `wait_s` to follow it. |

Look files go to `C:\Users\Sam\.rostrum\cache\look\`; every reply gives the full path. `look_frame` and `look_sheet` use the
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
| `painted-backgrounds` | you paint a big background in depth layers (far / mid / near) for camera moves and parallax |
| `3d-renders-in-2d` | you place a Rostrum3D item's render (product shot) in a comp, following new renders |
| `character-rigging-and-lip-sync` | you make a figure move from bones and IK, or make a mouth follow a voice |
| `camera-parallax-motion-blur` | you want a camera, depth between layers, motion blur, smears, trails |
| `import-and-export` | you bring in SVG, PDF, PSD, Figma, or hand over MP4, WebM, GIF, ProRes 4444, PNG sequence, Lottie |
| `easing-and-overlap` | you choose how a move travels (ease curves) and check that moves overlap as you meant |
| `text-on-a-path`, `curve-editor`, `expressions` | not yet: S10 (Team Sam) |

Each guide says what exists today, with the tool, operation or field name. Where something is planned but missing, it says
"not yet".
