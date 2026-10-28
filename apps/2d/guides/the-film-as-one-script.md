# The film as one script

The fastest way to a whole film is **one Python program** that makes every scene, every layer and every key, run with
`run_script`, looked at, edited and run again under the **same name**. A re-run merges: what you changed in the script
changes, what a person moved by hand stays. The small tools (`edit_document`, the `*.set` operations) are for quick
changes to one thing; a film written as many small calls, or as several scripts, is slower to change and easy to break.

This page is about how to **structure** that program. What each call does is in `start-here` (Scripts) and the topic
guides; the fragments here show the shape of a technique, not a piece to copy.

## The loop

1. Write the script to a file (`C:/work/film.py`) and run it: `run_script {"path": "C:/work/film.py", "look": true}`.
   `look: true` brings back, in the same reply, one contact sheet (3 tiles across) of 6 moments spread over the film
   (2.5 … 27.5 s on a 30 s film) and the film's weakest moments, most visible first (up to 8 lines in the summary, all
   of them in `data.look.faults`, each with its kind, start, end and words; the same checks as `look_review`).
   `look: [2, 7.5, 12, 18]` picks the moments (up to 12). It adds a few seconds to the call. If the stills fail, the
   merge still stands and the summary says "Look FAILED"; look again with `look_frame`. Beats of the brief are not
   checked here: `look_review` with `beats`, or the export's reply, checks them.
2. Read the faults and the sheet. Edit the file where the fault is.
3. Run it again with the same path (the file's name is the script's name). Repeat.
4. For detail, `look_frame` at one time (`area` for a zoom); `look_motion` for what moves when.
5. Export once it holds up: `render_export {"comp": "main", "format": "mp4"}` (or `render_video`) waits for its own file
   (`wait_s`, default 120 s, up to 600) and replies with the finished file, its checks and the weakest moments, so there
   is no job to poll. Past `wait_s` the reply says "Still running after N s" with the `inspect_job` call to make;
   `wait_s: 0` gives the job id at once. A failed export is an error, never a success.

Keep the same file and name for the whole session. A **new name adds a second copy** of everything; a second script
can't make a scene the first one made, nor key its layers (the refusal names the script that made them: add the lines
there and run that one).

## Timing in one place

Name every moment the film hangs on at the top as a shared marker, and derive the rest from the names:

```python
data = marker("data", 4)                 # a project marker (the same one edit_markers makes), gives "#data"
title_in = marker("title", "#data+11")   # a marker may be placed from another
b = beats(bpm=120, start=data)           # no song yet: a beat grid from the marker ("#data", "#data+0.5", …)
```

A marker time adds like a number (`data + 0.5` is `"#data+0.5"`) and every time in a script takes one: a key, a layer's
`start=` / `end=`, `tap(at=)`, `frame().cut(at=)`, `scramble(start=)`, `item.sample(start=)`. Keys and layers written
this way move when someone drags the marker; re-running the script puts its markers back where it says, and a
`marker()` line removed removes that marker (never a person's). `after(item, gap=0.2)` is the moment the item's last
key lands plus the gap. Music made in RostrumSound brings its own markers (`"#drop"`) and `beats()` (no `bpm`) reads the
song's beats in seconds. The music itself is never made in 2D: write it with RostrumSound's own `run_script` (guide `timing-to-music`).

## Scenes as functions of a start time

A scene that knows only its own start can move, shorten or swap places by changing one number:

```python
def scene_data_lines(t0):
    lines = [text(f"data{i}", body=line, font=MONO, size=28, x=180, y=300 + i * 44, start=t0, end=t0 + 5)
             for i, line in enumerate(LINES)]
    for t, line in stagger(lines, every=0.08, start=t0):
        line.key("opacity", {t: 0, t + 0.3: 1})

scene_data_lines(data)
```

Give every id a prefix from the scene (`data{i}`, `card_{i}`): ids are what match old to new on a re-run, and one id is
one item in the whole document.

## Your own helpers

The script is ordinary Python (functions, dicts, loops, list comprehensions; no classes, no imports beyond `math` and a
seeded `random`). Write the helpers your film repeats:

```python
def rise(item, at, by=40, dur=0.6):
    item.key("y", {at: (item.y + by, "snappy"), at + dur: item.y})
    item.key("opacity", {at: 0, at + dur * 0.5: 1})
```

## Place and frame by name, not by numbers

Raw coordinates are where a film written as one script goes wrong: a rectangle worked out by hand for the frame, a
card's `y` that overlaps the bar above it once a size changes. Let the calls do it:

- A product screen: `device("phone")` sizes and centres itself to the picture (`fit=`, `anchor="left"`); its screen
  is a column, so blocks made in it go one under the other. Any arrangement of cards, rows and titles: `row`,
  `column`, `grid`, `stack` with padding and gap (guide `lay-out-a-screen`).
- The camera: `frame().fit(["phone"], at=…, pad=0.06)` frames the device whole, `frame().fit(["hero"], at=…,
  pad=0.04)` pushes deep onto one part of it by id. Frame a device whole or one part of it, never most of it with the
  top or bottom nibbled off ("Framing a device" in the same guide).
- A tap: `tap(pointer(), layer("pay"), at=…)` lands the cursor's tip beside the button's words, with the press.

## A value from your own maths

When a field should follow a function you write (a spring, a noise walk, a value from a table), key it from Python:

```python
dot.sample("y", lambda t: 540 + 60 * math.sin(t * 2.4) * math.exp(-t * 0.4), start=3, end=9)
glow.sample("radius", [r for r in heights], start=12, every=2)      # a list: one value every 2 frames
```

`sample` writes one plain key per frame (linear between), so a person can drag them later. A formula that should stay a
formula in the document is `item.expr` (guide `expressions`).

## Many layers from a loop

Particles, list rows, bars, letters and drawings are loops. Seed per item so each is its own but the same on every run:

```python
for i in range(60):
    r = random(100 + i)
    size = r.uniform(6, 18)
    b = shape(f"bubble{i}", shape="ellipse", w=size, h=size, x=r.uniform(0, 1920), y=1200, depth=r.uniform(0.5, 4))
    b.key("y", {r.uniform(0, 4): 1200, 30: -100}, ease="linear")
```

Characters cycling into words are `scramble(id, body, start=,
end=)`; a number counting is `counter(...)`.

## Several scenes, one design

A design filled from many rows is one function called per row, each row its own scene (`comp(f"card_{i}", …)`), all
in the same script; then one `render_export` per scene (guide `data-math-and-graphs`, one design → many videos).

## When to use the small tools

- One value or key to try quickly: `edit_document` is fine. Once it is right, put it in the script too, so the script
  stays the whole film and the next re-run doesn't have to hold your edit back.
- A person's adjustments: leave them; the re-run reports them as held back.
