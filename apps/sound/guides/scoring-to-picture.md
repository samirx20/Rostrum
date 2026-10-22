# Scoring to picture with markers

How to make music and sound land on what happens in a video, and stay there when the edit or the tempo changes.
This page covers the tools; what the music should do is yours to decide.

## 1. See the picture

- **On the screen:** **+ Add › Picture to work to…** (or **+ Add › From a file…** with a video) opens the Picture panel
  at the arrangement's top right, with the video frame at the playhead. It plays along while you play. Pick a project
  item's latest render or a file; an item reference follows the item's newest render. Once a picture is set,
  **Picture** in the arrangement's header strip shows and hides it.
- **As an agent:** `look_video` with `video` = the file: `what: "sheet"` for the whole clip at a glance, `"motion"` for
  sudden stops and big moves (impact candidates, with times), `"frames"` around one time to check an event frame by frame.
  Every picture is labelled with time and frame number.
- The document's `picture` field (`doc.set`) is what the screen shows; set it so a person opening the song sees the same video.

## 2. Name the moments: markers, not numbers

A marker is a named time (`marker.add` with `name` and `at`). Anything else can then be placed **on the marker**:

| Time form | Means |
|---|---|
| `12.5` | 12.5 seconds from the start |
| `{"beat": 32}` | beat 32 on the song's tempo map |
| `"#logo"` | the marker named `logo` |
| `"#logo+0.5"` / `"#logo-1"` | half a second after / one second before it |

Put hits, clips, sections, automation points and look-tool checks on markers (`"#logo"`), never on a copied number.
When the cut moves, move the marker once (`marker.set`, or drag it on the arrangement's marker band) and everything on it
follows. Times keep the form they were written in: a drag on the screen never turns `"#logo+0.5"` into seconds.

Markers shared with other apps (a 2D "logo lands" read by Sound) come through the project service (`inspect_markers`
lists them; a project marker shows dashed on the marker band). Drag one there and it moves for every app, as one undo
step in the project's marker list; a local marker named like a project one is refused.

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
A swell (`dynamics`, the `swell` toggle) is drawn across the note's length, so it stretches with it and still peaks
where the note ends. A tie that would end at or before its note's start (a marker moved past it) fails the check and
the render, naming the note; it is never played as a silent note. Typing a length in the inspector sets a fixed one
(the tie is the agent's or the person's choice, kept until someone types over it).

## 3. Make the grid serve the picture

- **Tempo map:** `tempo.add` (`bpm`, `at`) adds a tempo change, `tempo.set` / `tempo.remove` edit it. On the screen,
  the tempo readout opens the tempo controls; tempo changes sit on the ruler and drag (one undo step per drag).
- To make a downbeat fall on a moment, work out the tempo from the gap: beats between two moments ÷ seconds between
  them × 60 = bpm. Check it with `look_beats` (below) rather than trusting the arithmetic.
- **Key:** `key.add` / `key.set` (`key` like `"D minor"`, `at`). **Sections:** `section.add` (`name`, `at`, `end`),
  `section.move` (`by`) moves a section and everything in it.
- Things placed in beats move when the tempo changes; things placed on markers or in seconds stay with the picture.
  Choose per element: music in beats, picture-locked hits on markers.

## 4. Check that it lands

1. `render_mix` (stems on), then `inspect_job` until done.
2. `look_events` with `expect` = the markers that should have a sound (`["#logo", "#door"]`) and `tolerance` (0.04 s =
   one frame at 25 fps). It answers each expected time's nearest onset and how many ms off. Use `track` to read one stem
   when the mix is busy, or `by_stem: true` to get, for every marker at once, which stem starts nearest it, how far off,
   and the mix's own nearest onset.
3. `look_beats` shows whether the music's own beats sit on the document's grid (per onset, ms from the nearest grid line).
4. `look_spectrum` with `marks` (`{"logo": "#logo"}`) draws the moments on the spectrogram, so a late or missing hit shows.

Read onset times as measurements: a soft sound reads 10–30 ms late. Whether a sound *fits* the image is decided by a
person watching and listening; say so in your report.

## Sound from motion

`edit_sounds_from_motion` turns a 2D animation's motion samples into placed sound events (see inspect_guide
`designed-sounds`). It is a starting placement to edit, not a finished track.
