# The film as one script

The fastest way to a whole film is **one Python program** that makes every scene, every layer and every key, run with
`run_script`, looked at, edited and run again under the **same name**. A re-run merges: what you changed in the script
changes, what a person moved by hand stays. The small tools (`edit_document`, the `*.set` operations) are for quick
changes to one thing; a film written as many small calls, or as several scripts, is slower to change and easy to break.

This page is about how to **structure** that program. What each call does is in `script-reference` and the topic
guides; the fragments here show the shape of a technique, not a piece to copy.

## The loop

1. Write the script to a file (`C:/work/film.py`) and run it: `run_script {"path": "C:/work/film.py", "look": true}`.
   `look: true` brings back one contact sheet (3 tiles across) of 6 moments spread over the film
   (2.5 … 27.5 s on a 30 s film); `look: [2, 7.5, 12, 18]` picks the moments (up to 12). It adds about a second to the
   call (the first look of a session a few seconds: the engine starts and the film is laid out once; after that a
   look draws only the frames asked, and a re-run sends the engine only what the script changed). If the stills fail, the merge still stands and the summary says "Look FAILED"; look again with `look_frame`.
   `notes: true` adds the checks' measurements at the end (the same ones `look_frame` with `what: "review"` lists),
   e.g. `Notes (n): [text_crossed:title] text 'X' crossed by 'ring' 10–85 %`. Notes are observations with numbers,
   never instructions; unasked, the reply carries none.
2. `look_frame` at the seconds you care about and judge the picture yourself. Change the script where you want it different.
3. Run it again with the same path (the file's name is the script's name). Repeat.
4. For detail, `look_frame` at one time (`area` for a zoom); `look_motion` for what moves when.
5. Export once it holds up: `render_export {"comp": "main", "what": "video"}` (the project render; `format: "mp4"` with a `path` for an mp4 of your own)
   returns at once with a job id and renders in the background from the document as it is at the call; keep working, then
   `inspect_job {"job_id": …, "wait_s": 25}` gives its progress and the finished reply (with `notes: true`, the checks'
   measurements too). `wait_s` (up to 600) waits in the call instead. Exporting again after a change re-renders only the
   2-second segments the change touches and reuses the rest (the reply says how many). A failed export is an error, never a success.

Keep the same file and name for the whole session. A **new name adds a second copy** of everything; a second script
can't make a scene the first one made, nor key its layers (the refusal names the script that made them: add the lines
there and run that one).

## Seeing your work: the look tools (use them every time)

You can't judge motion from the script. Look.

| Tool | Use it to |
|---|---|
| `look_motion` | Read **what moves and when** from the keys, no rendering: each layer's moves, path, peak speed, ease, overshoot, holds; entrances that overlap; where nothing moves; layers off screen at the end; keys that do nothing. Facts only. On screen means the engine draws it into the picture (groups, frame / camera, depth, tilt, drawing cycles counted). Short by default: a line a moving layer; identical findings (a hundred windows entering together) one line with a count and examples, the ones that matter first (never on screen, not on screen at the end, keys after the end, keys that do nothing, quiet stretches, overlapping entrances); at most 20 layers and 20 finding lines, then how many more; pass `layers` for just those, `limit` for more, `all` for no cap, `full` (with `layers`) for every move. Run it after every script. |
| `look_frame` (`what: "sheet"`) | See the **whole motion at a glance**: `count` frames (2–24) from `start` to `end` (seconds) in one labelled image `width` px wide (default 1600, the whole sheet: ~390 px tiles 4 across), `cols` tiles a row. For moments you pick (not evenly spaced) give `times: [0.5, 1.2, 3.0]` (to `look_frame`, with or without `what: "sheet"`): the same sheet. For detail, one `look_frame`. With `video: "<mp4 path>"` (with `sheet`, or `times`) the sheet is made of a **finished mp4's own frames**: the export itself, no item needed. |
| `look_frame` | See **one moment** in detail, at a time or frame number. Look at the landing frames and the hold frames. `area: [x, y, w, h]` (comp px) draws only that part, sharp at `width` (a zoom on a mouth or an edge); `times` + `cols` for a sheet of chosen moments. |
| `look_at` | Ask **what is at a point** (x, y, time; `space` frame or world): layers covering it, top first, with values (boxes are approximate). |
| `look_frame` (`what: "world"`) | See the **whole canvas** with the frame and its path drawn on it (a dot per frame, keys, cuts), and a ruler of world px. |
| `look_frame` (`what: "in_frame"`) | Ask **what is in the frame** at a time, or over a span: each layer in, partly in or out, and when it enters and leaves. |
| `look_frame` (`what: "empty"`) | Find **blank, pale and standing-still stretches** from tiny pictures every 0.5 s (seconds to run), with times and numbers: near-empty frames (almost only background), washed-out frames (all pale, low contrast), nothing moving for `min_still` s (default 2), and whether the piece ends on one. Facts, not verdicts: a held title is yours to judge. `video: "<mp4 path>"` checks a finished file. |
| `look_frame` (`what: "review"`) | List what the checks measure, most visible first, each with its times: a near-empty stretch, a text cut off by the frame edge (hand-lettered words, `paint.letters`, count as text in every text check, measured where their strokes are drawn so far), an old heading still faintly behind a new one, a set of parts (a chart's bars, a list's rows) not drawn in yet while the rest of its group shows, a plain card opening empty, a character's pose barely changing for 6 s or more, an arm held nearly straight for 4 s or more, a character's arms or legs thin next to its body (also named in `run_script`'s reply), framing held 10 s or more (no cut; it says what the camera did: nothing, or its travel such as "drifts 40 px over 0–68 s"), nothing moving, a subject cut by the edge (a layer blurred 20 px or more is atmosphere and never named), a title closer to the frame edge than the safe margin, a stray small dot that later grows (a wipe circle left showing), a layer showing outside the screen it belongs to (a cursor beside the phone), a lock-up whose parts touch, a frame nearly empty mid-film (under 10 % covered between 15 % and 85 % of the film), opening shots that look alike (the same layers on the same ground, about as big), the last picture held unchanged for over a fifth of the film, a text partly crossed (10–85 % of it, 1 s or more) by a layer drawn in front of it (a panel's own background counts; a text fully under a panel or sheet is hidden, not crossed; a frosted scrim never counts) with where to place the block instead ("place \"hero\" below \"nav\" (\"nav\" ends at y = 164 in \"home\" px): set \"hero\" y = 180", numbers in the px the script types, from where the block really draws), two cards or panels holding words that run into each other (measured where they really draw: a card whose words outgrow its h grows past it; with the y that puts the lower one clear, or a column(gap=…) so they never overlap; overlapping shapes without words, beams and glows are left alone), a group, picture or card that shows yet is never once in the picture, words with no padding on the card or sheet behind them (within ~0.4 of their letter height of its side, or past it), a ring or outline running through a text's letters whether drawn in front of it or behind it, a text cut by the edge of the screen or box that clips it, two showing texts on top of each other, a pointer (`pointer()`, or a layer named cursor, pointer, mouse, finger or hand) covering a fifth of a label or resting on its letters, an end card whose mark or lock-up is tiny in the frame, a layer in a device's screen hanging past the screen's edge (the outermost one, a card rather than its words; `overflow="hidden"` cuts it instead), a device (`device()`) cut by the frame edge where it is placed, or nibbled by camera push-ins while its sides show (with the frame key, the share of the film it is cut, and `frame().fit(["phone"], at=…, pad=0.06)` or a push onto one part; a push-in that fills the picture but still shows the device's body at a side of the frame (dark bars beside the screen) is named as a broken frame; a deep push-in filling the whole picture is meant and only listed in `data.info`, with the screen texts it cuts, except a label sliced by the edge, which is always named), a painted patch (a fill, or a wash in its outline) from a later paint layer of a drawing lying partly on a shape painted earlier, so it shows in front of it where they meet (lit windows over the awnings in front of the houses; paint it on a layer under that shape), a character more than half hidden behind layers in front of it, or standing on a bare set (fewer than 3 things or under 15 % of the frame besides it and the background), a layer an auto layout (row, column, grid, stack) jumps a large share of the frame in one frame with no key moving it (a sibling's size keyed on a hold: key the change over time, or animate with opacity / scale / shift, which never move the others). `beats: [{"at": 25, "to": 30, "expect": "camera move"}]` (also `cut`, `pose change`, `<layer id> moves`, `<layer id> shows`, `<layer id> reveals`: more of it showing over at..to, never whole before) names a beat of the brief that never happens or comes at the wrong time ("'lamp shows' already happened at 0 s; the beat is meant at 24 s"). A whole object made of several layers: name its group. Seconds to run on a 30 s film; `video` reads an exported mp4's pictures. Facts, not taste: a held title may be meant. |
| `render_export` (`what: "video"`) | Export the project render as an mp4, always under the name you asked. Always a job, run in the background: the call returns the job id at once and `inspect_job` with `wait_s` follows it (`wait_s` on the call waits for the file instead). A re-export draws only the 2-second segments a change touches. The finished reply names the one deliverable (`video`: your `path` copy, else the project render) and says whether it has sound (`has_sound`). It also checks the finished file (blank, washed-out or unchanged stretches: `quiet_stretches`; subjects cut by the edge: `edge_cuts`) and, with `notes: true`, ends with the review's measurements. Takes `beats` as the review does (checked only in notes). |

**The loop: write → run → look → change → export once.** Export replies end with the time left; add `notes: true` to
list what the checks measured. Give the brief's timed moments as `beats` ("the lamp is
revealed at the end": `{"at": 24, "to": 28, "expect": "lamp reveals"}`) if you want them measured. Look at the
composition after your last edit (`look_frame` `times: [..]`, or `what: "sheet"`): it is the export's picture without
an export, back in well under a second (only motion blur is left out; `quality: "final"` adds it). The review names
what can be measured, your eyes judge the rest. A sheet with `video` shows a file you already delivered.

## Using your time

A first version usually takes a fraction of the time you have: the rest is for looking at it (sheets of the whole span,
the export, single frames, zooms) and refining what you see, in passes.

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
