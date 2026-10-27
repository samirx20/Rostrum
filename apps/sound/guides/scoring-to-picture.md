# Scoring to picture with markers

How to make music and sound land on what happens in a video, and stay there when the edit or the tempo changes.
This page covers the tools; what the music should do is yours to decide.

## 1. See the picture

- **On the screen:** drag a video file from Explorer or the desktop onto the arrangement, or use **+ Add › Picture to
  work to…** (or **+ Add › From a file…** with a video). The Picture panel opens at the arrangement's right, under the last track when there is room there, else in its own column at the right with the tracks narrowed beside it (it never sits over a bar, so every bar stays clickable with the Editor open), with
  the video frame at the playhead. The song becomes at least as long as the picture, so you can mark the cuts before
  any music is written: type a time in the position field (`0:38`, Enter), then **M** (its name box opens: type a name and Enter; **Space** before you type plays on and keeps the name it was given, so M then Space marks a cut without stopping). It plays along while you play. Pick a project
  item's latest render or a file; an item reference follows the item's newest render. Once a picture is set,
  **Picture** in the arrangement's header strip shows and hides it. With a picture set, a click on the ruler's seconds
  line puts the playhead on the nearest whole frame of the picture (the bars line: the nearest grid line, marker or
  section edge); hold **Ctrl** to put it exactly where you click. A marker dragged on the ruler snaps the same way.
- **As an agent:** `look_video` with `video` = the file: `what: "sheet"` for the whole clip at a glance, `"motion"` for
  sudden stops and big moves (impact candidates, with times), `"frames"` around one time to check an event frame by frame.
  Every picture is labelled with time and frame number.
- The document's `picture` field (`doc.set`) is what the screen shows; set it so a person opening the song sees the same video.

## 2. Name the moments: markers, not numbers

A marker is a named time (`marker.add` with `name` and `at`). Anything else can then be placed **on the marker**:

| Time form | Means |
|---|---|
| `12.5` | 12.5 seconds from the start (a bare number is always seconds) |
| `{"beat": 32}` | beat 32 on the song's tempo map (a time says `beat`; a length says `{"beats": n}`) |
| `"#logo"` | the marker named `logo` (a name with spaces as written: `"#logo lands"`) |
| `"#logo+0.5"` / `"#logo-1"` | half a second after / one second before it |

Put hits, clips, sections, automation points and look-tool checks on markers (`"#logo"`), never on a copied number.
Mark the cuts first, then write: a script names the song's markers (made with `marker.add` or on the screen) and the
project's as `"#logo"` without restating them; `marker("logo", at=...)` in a script makes a marker of its own.
When the cut moves, move the marker once (`marker.move`: `edit_markers` for a project marker, `edit_document` for one of the song's own,
the same name for both; `marker.set` is read as it, `inspect_operations name=marker.move` answers as marker.set, and an error names the one you sent; `edit_markers` times are seconds only (a plain number): for beats or a time on another marker use `edit_document`; or drag it on the arrangement's marker band) and everything on it
follows. **A lead-in is tied to the cut it builds to, not to where it was written.** A riser written `"#tense+4.5"` follows `#tense`, so when `#reveal` moves it stays behind and the build ends before the cut. Pass `lead_in` on the move: `edit_markers {"ops": [{"op": "marker.move", "target": ["reveal"], "args": {"at": 26, "lead_in": 4}}]}` (seconds, or `{"beats": 8}`) first re-times everything of the open songs that starts within that window before the marker onto it (`"#reveal-1.5"`, the same moment, a step in that song's history), then moves the marker, and the build goes with it. For a marker of the song's own, or to carry without moving, call `marker.carry {marker: "reveal", lead_in: 4}` through `edit_document` first. Without `lead_in` nothing else moves, and the reply warns when notes, hits or clips end within a beat before the marker ("3 notes on strings end just before #reveal and stay when it moves: pass lead_in to carry them"). Run the carry after the last re-run of a script that wrote those times: a script that writes `"#tense+4.5"` again puts it back. Times keep the form they were written in: a drag on the screen never turns `"#logo+0.5"` into seconds.
On the screen, **right-click a marker** to rename it, colour it, move it to the playhead, loop up to the next marker, put a sound there, start a bar there, or delete it. One spot holds one marker: `marker.add` at a time that already has one fails and names it (rename or move that one instead), and **M** there selects it and opens its name.

Markers shared with other apps (a 2D "logo lands" read by Sound) come through the project service (`inspect_markers`
lists them after the song's own markers, which it lists first as `song_markers`; a project marker shows dashed on the marker band). Drag one there and it moves for every app, as one undo
step in the project's marker list; a local marker named like a project one is refused, and a MIDI import leaves out (with a warning) file markers named like a project marker.

### Held parts: tie both ends

A note placed on a marker moves with it, but a fixed length (`"dur": 1.25`) does not: if the marker after it moves
later, a pad or a string chord that was written to reach the marker now stops short and leaves a gap. Tie the end
instead:

| Length form | Means |
|---|---|
| `1.25` / `{"beats": 2}` | a fixed length (it does not follow anything) |
| `{"to": "#land"}` | ends at the marker `land` (any time form: `{"to": {"beat": 16}}`, `{"to": "#land-0.1"}`) |
| `"next"` | holds until the next note on the same track starts (the last note: until the mix's `length`) |

So a pad that swells into "land" and holds to the end is two notes: `at "#spark", dur "next"` and
`at "#land", dur {"to": "#end"}`. Move "land" and the first note grows, the second shrinks, and there is never a gap.
The same goes for a cue's last notes: put a marker on the cue's end (`marker("end", at=20)`) and tie them to it
(`end="#end"` in a script, `{"to": "#end"}` in an operation; `end="#end" + beats(2)` ends two beats after it). A note at
`"#drop+5"` that ends at a fixed `19.5` breaks when the drop moves later (it would end before it starts, and the render
refuses it, naming the note and writing out the fix); tied to `"#end"` it just gets shorter.
A swell (`dynamics`, the `swell` toggle) is drawn across the note's length, so it stretches with it and still peaks
where the note ends. A tie that would end at or before its note's start (a marker moved past it) is a warning in every
reply and the Problems list, naming the note, and the render refuses it; it is never played as a silent note, and the
song still opens. `look_arrangement` still draws the song: such notes are drawn short and listed under `broken_notes`;
`inspect_diagnose` labels them `broken-tie` (a part starting after the song's end: `after-the-end`; one still held at it: `held-past-end`). Typing a length in the settings panel sets a fixed one
(the tie is the agent's or the person's choice, kept until someone types over it).

## 3. Make the grid serve the picture

- **Tempo map:** `tempo.add` (`bpm`, `at`, `ramp`) adds a tempo change, `tempo.set` / `tempo.remove` edit it. With
  `ramp: true` the tempo glides evenly from this change's bpm to the next change's (an accelerando into a reveal, a
  slow-down into the last shot); the flag on the ruler reads "♩ 100 ↗" or ↘. On the screen, the tempo field in the header
  strip edits the tempo playing at the playhead: the song's own tempo (the whole song, when it has no changes) or the
  tempo change in force there; it adds no change. To change the tempo from a moment on, put the playhead there and
  press **+ Tempo change**. A flag's panel has **Bpm**, **At** and **Glide to next**; flags drag on the ruler (one undo
  step per drag). A typed tempo keeps its decimals (99.5 bpm); a drag moves in whole bpm.
- **Time signature:** `meter.add` (`beatsPerBar`, `beatUnit`, `at`) starts a new bar at that beat, until the next
  change: 3 and 4 is 3/4; 6 and 8 is 6/8, a bar of six eighths whose click plays its two main beats. A beat unit left
  out is 4. `meter.set` / `meter.remove` edit it. The ruler's bar numbers, the grid and the click follow it. On the
  screen, select nothing: the settings panel lists every tempo, time signature and key change; **+ Time signature
  change** adds one on the bar line nearest the playhead (a change always starts a whole bar: `meter.add` / `meter.set`
  off a bar line is refused, naming the nearest bar lines) and its panel has **Beats per bar** and **Beat unit**.
- **To make a bar line fall on a marker, use `tempo.fit_bar`** (`edit_document`): `{"op": "tempo.fit_bar", "args": {"marker": "logo lands", "bar": 13}}`
  sets the tempo so bar 13 starts exactly on the marker "logo lands" (everything written in beats follows). The marker must be
  placed in seconds (the picture's, or one from 2D; a marker on a beat is refused), and `bar` is 2 or more. Checked: a marker at 25.0 s with
  `bar: 13` turned a 96 bpm song into 115.2 bpm (12 bars of 4 beats in 25 s). With a tempo change before that bar, the tempo in force
  at that bar is the one set. Check the result with `look_arrangement` and `look_music` (`what: "beats"`).
- **Key:** `key.add` / `key.set` (`key` like `"D minor"`, `at`). **Sections:** `section.add` (`name`, `at`, `end`),
  `section.move` (`by`) moves a section and everything in it, except markers: the picture's cut points stay put.
- Things placed in beats move when the tempo changes; things placed on markers or in seconds stay with the picture.
  Choose per element: music in beats, picture-locked hits on markers.

## 4. Check that it lands

1. Before rendering, `look_arrangement`: per marker, which tracks start on it (within 10 ms) and how far off the
   others are, in ms and beats, with a picture of every part against the markers.
2. `render_mix` (stems on), then `inspect_job` until done.
3. `look_music` (`what: "events"`) with `expect` = the markers that should have a sound (`["#logo", "#door"]`) and `tolerance` (0.04 s =
   one frame at 25 fps). It answers each expected time's nearest onset and how many ms off. Use `track` to read one stem
   when the mix is busy, or `by_stem: true` to get, for every marker at once, which stem starts nearest it, how far off,
   and the mix's own nearest onset.
4. `look_music` (`what: "beats"`) says whether the audio's beats fit the document's tempo, and shows whether the music's own beats sit on the document's grid (per onset, ms from the nearest grid line).
5. `look_sound` (`what: "spectrum"`) with `marks` (`{"logo": "#logo"}`) draws the moments on the spectrogram, so a late or missing hit shows.

Read onset times as measurements. The engine compensates each recorded instrument's attack, so a note written at a marker
is heard at the marker; the offsets that remain are small (measured: brass, horn, tuba and harp read 1–11 ms late; a very soft start reads
late because onset detection finds a soft sound after it begins). If a stem still reads consistently early or late by more
than your tolerance, write that stem's notes that many ms off the marker (`"#logo-0.02"`), one change at a time, and check
again with `look_music` (`events`, `by_stem: true`). A soft or masked start (strings under a sustained chord) may show no onset
at all: read that stem's own row, not the mix's nearest onset. Whether a sound *fits* the image is decided by a
person watching and listening; say so in your report.

## Sound from motion

`edit_sounds_from_motion` reads a 2D animation's motion samples and suggests musical answers (a hit or note on a
landing, a rise built from an instrument, or nothing). It adds a sound only when asked, and only music or a real
recorded sound (see inspect_guide `scoring-motion`). Score motion with instruments on named markers: a string rise, a
cymbal swell or a piano run into a landing, a struck bell or hit on it, a held silence before a big change.
