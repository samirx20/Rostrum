# Writing parts with the piano roll and MIDI

How notes get into a track, by hand, from a keyboard, from a file or from a script, and how to check them.
The script API is in inspect_guide `script`; instruments in `library`.

## Units agents must know

- **A bare number for a time or a length is SECONDS**, everywhere (`at: 4` is 4 s, never bar 4 or beat 4).
- **Beats:** a time is `{"beat": 8}` (singular, counted from 0 at the start); a length is `{"beats": 2}` (plural). Using the
  wrong one is refused and says which to use. Bars and "5.3" are for typing on the screen; in operations and scripts use
  `{"beat": n}` (or `bar(n)` in a script).
- **Volume:** a bare number is gain 0 … 4 (1 = 0 dB, 0.5 = -6 dB, 2 = +6 dB). The screen shows dB; agents may give dB too:
  `"volume": {"db": -6}` or `"volume": "-6 dB"` on a track, bus, clip, line or the master. **Every built-in
  instrument, played instrument, synth wave and the built-in kit is level-matched** (measured: a typical comp, bass, lead
  line, pad or groove for each comes out equally loud), so tracks written as the part each suits (the table below) at
  the same volume are roughly balanced: a piano comp at 0 dB sits with the bass and drums at 0 dB. Roughly, not exactly:
  the same chord on every sound spreads about 11 dB, so check with `look_sound` (`what: "levels"`) after the first render. How hard you play (`vel`) and how many notes you stack are still loudness: a five-note chord at vel 0.5
  is quieter than a bass note at 0.9. Sampled (SFZ), plug-in and recorded sounds are not matched (their level is the file's).
- **The song's length** (`length`) is where it ends, a time: `bar(9)` is where bar 9 starts, so `length(bar(9))` is an
  8-bar song. For N bars write `length(bar(N+1))`. `run_script` and `inspect_item` (the song) end with the length in
  bars and seconds ("8 bars long (ends where bar 9 starts, 20.0 s)").
- **The song itself** is the item `"root"`: `{"op": "doc.set", "target": ["root"], "args": {"tempo": 96}}`. (`inspect_operations`
  lists item *types* in its target column; the ids come from `inspect_item`.)

## Which sound for which part

Every built-in sound is made for a part; its level is matched on the first part listed. `inspect_engine` lists the same
table (`roles`), `inspect_engine (what "instrument") builtIn=… / model=… / synth=…` gives one sound's line. Synthesized sounds play any
key; "sounds best" is where they sound like themselves.

| Part | Sounds (`builtIn` / `model` / `synth` / `kit`) | Sounds best |
|---|---|---|
| comp (chords that keep time) | feltPiano, grandPiano, spiccatoStrings; model guitar, nylonGuitar | C2-C6 (strings G2-E6, guitars E2-E5) |
| bass (the low line) | subBass (synth sine also works as a sub under it) | E1-G3 |
| lead (a tune on top) | glassMarimba; model marimba, vibraphone, glockenspiel (keep it quiet), tubularBell (single strikes), violin; synth triangle, sine | C4-C7 (glockenspiel G5-C8, violin G3-E7, bell C4-F5) |
| pad (held chords under everything) | warmPad, analogStrings, choirPad, cinematicBrass; synth saw, square | C2-C6 (choir C3-C6, brass E2-C5) |
| groove (drums) | kit synth | kick, snare, clap, hat, openHat, cymbal, tom, rim |

Pianos, guitars, marimba, vibraphone, brass and the saw and square waves also play leads (`inspect_engine` lists every
part each suits). Sampled (SFZ) instruments carry their own range (`inspect_engine (what "instrument") sfz=<path>`) and are not
level-matched.

## Notes are data

A note is `pitch` (MIDI number, 60 = middle C; the screen shows and takes names like G4), `at` (a time: seconds, `{"beat": n}` or `"#marker"`), `dur` (seconds
or `{"beats": n}`; note the plural), `vel` (0..1), plus the instrument's own playing settings when they apply (an articulation `art`
on an articulated SFZ, `position` / `damping` on a plucked string, `bend`, `vibrato` …). Only the settings the track's
instrument can use are offered (the screen hides the rest). On the screen a note's At and Length read in bars.beats (At **5.3** = bar 5, beat 3; Length reads as a note value when it is one: **1/8**, **1/4**, **dotted 1/4** … , else words (**1 beat**, **2 bars 1 beat**); hover it for the seconds) and take `5.3`, `1/8` or `1 bar 2 beats` (a length), `9.6 s` or `0:09.6` typed (the old `0.2` and `5.3.480` still work); the file keeps the form it had. Drum tracks use hits (`hit.add`: `drum`, `at`, `vel`).

- One note: `note.add`. Many in one undo step: `note.add_many` with `notes`. Change: `note.set`. Remove: `note.remove`.

## On the screen

- **A new track** starts from a sound in the **Library** (Ctrl+L): every row has its own **Add**, and Add always makes a new
  track. To change a track's sound, pick another in the **Sound ▾** field of its settings panel (the notes stay).
- **Editor** (the dock under the arrangement, E; the selected track): it opens tall (about three quarters of the room under the arrangement) and framed on the track's notes (keys never smaller than 9 px; the view scrolls if the part is wider), beside a
  piano keyboard (a C label on every octave; click a key to hear it on the track's instrument). Its top line, beside
  the Editor / Mixer tabs, holds the track's name, **Select** (V) / **Draw** (B) and **Note ▾** (how long a new note
  is). Double-click to add, or the **Draw** tool where every click adds, in the grid cell under the pointer; drag to move (it snaps to the grid set by **Grid ▾**, with **Snap** on; Ctrl = no snapping,
  Alt = a copy, Shift = only in time), drag the end to lengthen, Delete removes. Each drag
  is one undo step (a note drawn with the Draw tool, dragged long, too: "Draw note"); the new note is selected. Clicks in the roll never move the playhead and the view never scrolls by itself. Drum tracks show a row per drum. Select several (Ctrl+click, Shift+click, a box) and act on them
  from the top of the settings panel, the right-click menu or keys: Q quantise, Ctrl+D duplicate, ↑ / ↓ a half step.
- **Velocity strip** (under the notes): one bar per note, as high as it plays loud. Drag a bar, or draw a line
  across several. The value of the bar under the pointer (or of the selected notes) is written beside it ("70 %").
- **Playing lane** (under the velocity strip, for an instrument that plays notes; folded to one line "› Sustain · Expression · Bend" while the track has none of them: click it to open): the picker at its head (it names the lane, "Sustain ▾") chooses **Sustain** (the pedal: up
  at the bottom, down at the top; a note let go while it is down rings on until it lifts), **Expression** (how loud
  the whole part plays, like a swell on the strings) or **Bend** (the pitch wheel: the middle is no bend, the top
  and bottom are up and down by the track's **Bend range**, 2 semitones unless you change it in the settings panel).
  Click to add a point, drag it, Delete removes it; one drag is one undo step. It is the same lane as the track's
  Auto lanes in the arrangement, and it folds away with the velocity strip.
- **MIDI keyboard:** choose the input device (shown only when one is connected), arm the track, record: what you play
  lands in the selected track's piano roll as one undo step for the whole take.
- The song's tempo, beats per bar and key are fields in the arrangement's header strip; they edit what plays at the
  playhead. With nothing selected, the settings panel lists every tempo, time signature and key change, the sections
  and markers (click one: the playhead jumps there), each list with its **+** for the playhead. A tempo flag on the ruler can **Glide to next**. Notes written in beats follow tempo changes.

## From a file and back

- `edit_import_midi` with `path` = a `.mid` file: one track per part (channel 10 becomes drum hits), its markers and
  sections, and with `song_map` the tempo map and key. The sustain pedal (CC 64), expression (CC 11), mod wheel
  (CC 1) and pitch wheel come in as the part's Sustain, Expression, Vibrato and Bend lanes (its bend range too).
- `render_mix` (`what: "midi"`) writes the document's notes and those lanes as a `.mid` for other tools. On the screen: Export
  (Ctrl+E) › What for › **MIDI file**, the same file.
- Agents set the lanes with `automation.set` on the track: lane `sustain` (0 up … 1 down), `dynamics` (expression,
  0 … 2, 1 = as played), `bend` (-1 … 1 × `bendRange` semitones, `track.set {bendRange}`: a track with no bend lane yet takes it only in the
  same call as the lane, in either order); a step is two points at
  one time. In a script: `t.sustain([...])`, `t.dynamics([...])`, `t.bend([...], range=2)` (see `script`).

## From a script

`run_script` builds tracks and notes in Python. Re-running a script merges: notes a person moved by hand stay where
they were put and are listed as held back. Helpers write plain values you can edit afterwards, e.g. seeded
`humanize(seed, timing, velocity)` for small timing and velocity variation (see `script`). The operation for
notes already written is `note.humanize`, with note ids as its targets (not the track).

## Checking the part

- `look_music` (`what: "harmony"`) (`track` optional): the key, the chord per bar or beat, and plain facts about the written notes:
  notes outside the instrument's range, voices crossing, close intervals low down, notes out of key. Chord and note names
  are spelled for the key (flats in flat keys).
- `look_music` (`what: "pitch"`) with `track` after a render: the notes heard against the notes written (wrong note, wrong octave, early,
  late, out of tune, missing). One line at a time: read a single-voice stem.
- `look_music` (`what: "beats"`): whether the played notes sit on the grid, per onset in ms.

These report facts; whether a line is musical is decided by listening.
