# Scoring to picture with markers

How to make music and sound land on what happens in a video, and stay there when the edit or the tempo changes.
This page covers the tools; what the music should do is yours to decide.

## 1. See the picture

- **On the screen:** Timeline › "Picture" in the piano roll's header opens a corner with the video frame at the playhead.
  It plays along while you play. Pick a project item's latest render or a file; an item reference follows the item's
  newest render.
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
When the cut moves, move the marker once (`marker.set`, or drag it on the Timeline's marker band) and everything on it
follows. Times keep the form they were written in: a drag on the screen never turns `"#logo+0.5"` into seconds.

Markers shared with other apps (a 2D "logo lands" read by Sound) come through the project service; until it lists them,
`inspect_markers` answers empty with a warning. Put the same name in both documents and keep one source in mind.

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
   when the mix is busy.
3. `look_beats` shows whether the music's own beats sit on the document's grid (per onset, ms from the nearest grid line).
4. `look_spectrum` with `marks` (`{"logo": "#logo"}`) draws the moments on the spectrogram, so a late or missing hit shows.

Read onset times as measurements: a soft sound reads 10–30 ms late. Whether a sound *fits* the image is decided by a
person watching and listening; say so in your report.

## Sound from motion

`edit_sounds_from_motion` turns a 2D animation's motion samples into placed sound events (see inspect_guide
`designed-sounds`). It is a starting placement to edit, not a finished track.
