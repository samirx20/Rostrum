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
- **Editor** (the dock under the arrangement, E; the selected track): double-click to add, or the **Draw** tool (B)
  where every click adds; drag to move (it snaps to the grid set by **Grid ▾**, with **Snap** on; Ctrl = no snapping,
  Alt = a copy, Shift = only in time), drag the end to lengthen, Delete removes. Each drag
  is one undo step. Drum tracks show a row per drum. Select several (Ctrl+click, Shift+click, a box) and act on them
  from the context bar, the right-click menu or keys: Q quantise, Ctrl+D duplicate, ↑ / ↓ a half step.
- **MIDI keyboard:** choose the input device (shown only when one is connected), arm the track, record: what you play
  lands in the selected track's piano roll as one undo step for the whole take.
- The song's tempo, beats per bar and key are in the settings panel while nothing is selected; tempo and key changes
  at the playhead come from the tempo · beats · key readout in the arrangement's header strip. Notes written in beats
  follow tempo changes.

## From a file and back

- `edit_import_midi` with `path` = a `.mid` file: one track per part (channel 10 becomes drum hits), its markers and
  sections, and with `song_map` the tempo map and key.
- `render_midi` writes the document's notes as a `.mid` for other tools.

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
