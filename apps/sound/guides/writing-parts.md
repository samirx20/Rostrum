# Writing parts with the piano roll and MIDI

How notes get into a track, by hand, from a keyboard, from a file or from a script, and how to check them.
The script API is in inspect_guide `script`; instruments in `library`.

## Notes are data

A note is `pitch` (MIDI number, 60 = middle C), `at` (a time: seconds, `{"beat": n}` or `"#marker"`), `dur` (seconds
or `{"beats": n}`), `vel` (0..1), plus the instrument's own playing settings when they apply (an articulation `art`
on an articulated SFZ, `position` / `damping` on a plucked string, `bend`, `vibrato` …). Only the settings the track's
instrument can use are offered (the screen hides the rest). Drum tracks use hits (`hit.add`: `drum`, `at`, `vel`).

- One note: `note.add`. Many in one undo step: `note.add_many` with `notes`. Change: `note.set`. Remove: `note.remove`.

## On the screen

- **A new track** starts from a sound in the **Library** (Ctrl+L): double-click an instrument. With a notes track
  selected the Library offers to change its instrument instead (the notes stay).
- **Editor** (the dock under the arrangement, E; the selected track): it opens framed on the track's notes, beside a
  piano keyboard (a C label on every octave; click a key to hear it on the track's instrument). Its top line, beside
  the Editor / Mixer tabs, holds the track's name, **Select** (V) / **Draw** (B) and **Note ▾** (how long a new note
  is). Double-click to add, or the **Draw** tool where every click adds; drag to move (it snaps to the grid set by **Grid ▾**, with **Snap** on; Ctrl = no snapping,
  Alt = a copy, Shift = only in time), drag the end to lengthen, Delete removes. Each drag
  is one undo step. Drum tracks show a row per drum. Select several (Ctrl+click, Shift+click, a box) and act on them
  from the top of the settings panel, the right-click menu or keys: Q quantise, Ctrl+D duplicate, ↑ / ↓ a half step.
- **Velocity strip** (under the notes): one bar per note, as high as it plays loud. Drag a bar, or draw a line
  across several. The value of the bar under the pointer (or of the selected notes) is written beside it ("70 %").
- **Playing lane** (under the velocity strip, for an instrument that plays notes): pick **Sustain** (the pedal: up
  at the bottom, down at the top; a note let go while it is down rings on until it lifts), **Expression** (how loud
  the whole part plays, like a swell on the strings) or **Bend** (the pitch wheel: the middle is no bend, the top
  and bottom are up and down by the track's **Bend range**, 2 semitones unless you change it in the settings panel).
  Click to add a point, drag it, Delete removes it; one drag is one undo step. It is the same lane as the track's
  Auto lanes in the arrangement, and it folds away with the velocity strip.
- **MIDI keyboard:** choose the input device (shown only when one is connected), arm the track, record: what you play
  lands in the selected track's piano roll as one undo step for the whole take.
- The song's tempo, beats per bar and key are fields in the arrangement's header strip; they edit what plays at the
  playhead. With nothing selected, the settings panel has **+ Tempo change**, **+ Key change** and **+ Section** for the
  playhead. A tempo flag on the ruler can **Glide to next**. Notes written in beats follow tempo changes.

## From a file and back

- `edit_import_midi` with `path` = a `.mid` file: one track per part (channel 10 becomes drum hits), its markers and
  sections, and with `song_map` the tempo map and key. The sustain pedal (CC 64), expression (CC 11), mod wheel
  (CC 1) and pitch wheel come in as the part's Sustain, Expression, Vibrato and Bend lanes (its bend range too).
- `render_midi` writes the document's notes and those lanes as a `.mid` for other tools. On the screen: Export
  (Ctrl+E) › What for › **MIDI file**, the same file.
- Agents set the lanes with `automation.set` on the track: lane `sustain` (0 up … 1 down), `dynamics` (expression,
  0 … 2, 1 = as played), `bend` (-1 … 1 × `bendRange` semitones, `track.set {bendRange}`); a step is two points at
  one time. In a script: `t.sustain([...])`, `t.dynamics([...])`, `t.bend([...], range=2)` (see `script`).

## From a script

`run_script` builds tracks and notes in Python. Re-running a script merges: notes a person moved by hand stay where
they were put and are listed as held back. Helpers write plain values you can edit afterwards, e.g. seeded
`humanize(seed, timing, velocity)` for small timing and velocity variation (see `script`).

## Checking the part

- `inspect_harmony` (`track` optional): the key, the chord per bar or beat, and plain facts about the written notes:
  notes outside the instrument's range, voices crossing, close intervals low down, notes out of key. Chord and note names
  are spelled for the key (flats in flat keys).
- `look_pitch` with `track` after a render: the notes heard against the notes written (wrong note, wrong octave, early,
  late, out of tune, missing). One line at a time: read a single-voice stem.
- `look_beats`: whether the played notes sit on the grid, per onset in ms.

These report facts; whether a line is musical is decided by listening.
