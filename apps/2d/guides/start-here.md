# Start here: Rostrum2D

Rostrum2D makes motion graphics: type, shapes, screens, drawings, characters. You and a person edit **the same
document**: what you build stays editable by hand, and what they move stays moved. This page is the whole way of
working on one page; the topic guides at the end hold the detail.

## The loop

1. **Write ONE script** for the whole film, to a file (`C:/work/film.py`).
2. **Run it with look:** `run_script {"path": "C:/work/film.py", "look": true}`. The reply brings a contact sheet.
   Add `notes: true` to get the checks' measurements at the end (what is crossed, cut, empty, and when).
3. **Look** with `look_frame` at the seconds you care about (a frame in seconds) and judge it yourself. A look is
   what the canvas shows at that moment, like a screenshot of the window while scrubbing: well under a second on any
   film, so look often. It needs no export: transitions, camera, depth of field, paint and text are drawn as the
   export draws them; only motion blur is left out (`quality: "final"` adds it for one look).
4. **Change the script**, not the document.
5. **Re-run under the SAME name** (the same path). A re-run merges: what you changed changes, what a person moved
   by hand stays. A new name adds a second copy of everything.
6. **Export once**, when the looks say it is done, with `render_export {"what": "video"}`: it waits for the file and
   always writes what you asked under the name you gave. An export is for delivering, not for checking a moment. `notes: true` adds what the checks measured; they are observations, never required.

Every reply ends with a clock line. Use the time to look and refine in passes; `inspect_project` with
`what: "session"` lists what you have not checked yet.

## Lay out first

Place things with boxes, not x / y sums. `row`, `column`, `grid(columns=3)` and `stack` place and size what you make
inside them:

- `padding`, `gap`, `align` (`start` `center` `end` `stretch`), `justify` (`start` `center` `end` `between` …).
- Sizes in px, `"50%"`, `"fill"` or `"fit"`; `grow=1` takes the room left; texts wrap where the box ends.
- Inside a box, `x=` / `y=` fail (the box places the layer) unless you give `apart=True` (a badge, a pointer).
- **A layer with no `x`, `y` sits at its parent's centre** (the frame's middle, or its group's). `x`, `y` place its
  anchor, the centre by default: `x=960` centres it on a 1920-wide frame whatever its size.
- **Named anchors:** `anchor="top-left"`, `"top"`, `"bottom-left"`, `"bottom-right"`, `"center"` … say which point
  of the layer its `x`, `y` place, and where it turns and grows from (`anchor="bottom"` grows a bar up from its floor).

Keep raw `x`, `y` for motion and art: a moving shape, a painted world, a camera path.

## Time by name

- `marker("reveal", 3)` makes a shared project marker at 3 s and gives `"#reveal"`. It adds like a number:
  `"#reveal+0.5"`. Any time takes it: a key, `start=`, `end=`. Drag the marker (here or in Sound) and everything
  timed from it moves.
- `after(item, gap=0.2)`: the moment an item's last key lands, plus a gap.
- `stagger(items, every=0.1, start=)`: `[(time, item), …]`, each one `every` seconds after the one before.
- `beats()`: the song's beats in seconds; `beats(bpm=120, start=)` a beat grid when there is no song yet.

Never hand-count times like `t0 + i * 0.5`.

## Keys and ease

A field is still (one value) or animated (keys). `item.key("opacity", {0.0: 0, 0.6: 1}, ease="easeOut")`: each key
is a value at a time; the **first key's ease** shapes the way to the next. Before the first key the value holds the
first key's value. Eases: `linear`, `hold`, `smooth`, `snappy`, `natural`, `heavy`, `easeIn`, `easeOut`,
`easeInOut`, `spring`, `bounce`.

## A tiny example

The technique only, not a piece to copy:

```python
comp("main", width=1920, height=1080, fps=30, duration=6, background="#101014")
go = marker("go", 1.0)                                   # gives "#go"
with column("list", gap=24, align="start"):              # no x / y: centred in the frame
    rows = [text(f"row{i}", body=w, size=72) for i, w in enumerate(["One", "Two", "Three"])]
for t, row in stagger(rows, every=0.15, start=go):
    row.key("opacity", {t: 0, t + 0.4: 1}, ease="easeOut")
    row.key("shiftY", {t: 30, t + 0.4: 0}, ease="easeOut")
text("tag", body="v2", size=36, anchor="bottom-left", x=80, y=1000, start=after(rows[-1], gap=0.3))
```

## The five core tools

- `run_script`: build or change the whole film from your script; `look: true` checks it in the same reply.
- `look_frame`: see one moment, or `what: "sheet"` (a contact sheet), `"review"` (the checks' measurements), `"diagnose"`
  (what is broken), `"world"`, `"in_frame"`, `"empty"`.
- `look_motion`: what moves and when, read from the keys (no picture).
- `inspect_guide`: these guides; `{"topic": "script-reference"}`, and `section` for one part of a long one.
- `render_export`: deliver. `what: "video"` is the project's mp4; `format` gives the Export button's formats (WebM,
  GIF, ProRes, PNG, Lottie …).

**Never** place by picture coordinates inside a device, row or column, and never hand-compute a position or a time
that the layout, an anchor or a marker can give you.

## Where next

- `script-reference`: every script function and field, ids, keys, effects, re-run rules, the first-time surprises,
  reading errors.
- `the-film-as-one-script`: how to structure the whole film; every look tool; using your time.
- `lay-out-a-screen`: rows, columns, grids, stacks, Tailwind words (`tw=`).
- `timing-to-music`: markers, layers timed from a marker, beats, the song from RostrumSound.
- `ui-and-product-animation`: devices, screen blocks, counters, pointers, glass and depth.
- `styled-words`: one text, some words styled and keyed on their own (`body=[…]`, `text.run()`).
- `tap-and-react`: `tap()` aims at the centre, follows a moving target, reacts (`then=`).
- `lower-thirds-and-charts`: `lower_third` (name + role on a bar) and `chart` (bars or a line with axes): place, colour, time, take apart.
- `type-and-kinetic-text`: fonts, per-letter animation (typing on: key opacity 0 → 1 with `letterDelay`), scrambles.
- `easing-and-overlap`: what each ease does, checking overlap.
- `frame-parallax-motion-blur`: moving and cutting the frame, depth, motion blur.
- `transitions-and-carry-overs`: `transition()` (cut, fade, push, slide, wipe, iris, zoom, blur) and `carry()` from one section to the next.
- `shape-and-path-animation`: the pen, combining shapes, drawing a stroke on.
- `drawing-and-frame-by-frame`, `painted-backgrounds`: brush strokes, one picture per frame, big painted worlds.
- `character-rigging-and-lip-sync`: limbs, poses, walks, mouths that follow a voice.
- `data-math-and-graphs`: plots, axes, charts from a table.
- `colour-and-blending`, `expressions`, `text-on-a-path`, `curve-editor`: blend modes and grades; a field from a
  formula; text along a curve; easing by hand.
- `import-and-export`, `3d-renders-in-2d`, `files`: files in and out, a Rostrum3D render in a comp, opening projects.
- `the-screen`: the window, for when you help a person by hand.
- `tools-in-detail`: every tool and argument in full (the tool list keeps one line each).
