# Writing parts with the piano roll and MIDI

How notes get into a track, by hand, from a keyboard, from a file or from a script, and how to check them.
The script API is in inspect_guide `script`; instruments in `library`.

## Units agents must know

- **A bare number for a time or a length is SECONDS**, everywhere (`at: 4` is 4 s, never bar 4 or beat 4).
- **Beats:** a time is `{"beat": 8}` (singular, counted from 0 at the start); a length is `{"beats": 2}` (plural). Using the
  wrong one is refused and says which to use. Bars and "5.3" are for typing on the screen; in operations and scripts use
  `{"beat": n}` (or `bar(n)` in a script).
- **Volume:** a bare number is gain 0 … 4 (1 = 0 dB, 0.5 = -6 dB, 2 = +6 dB). The screen shows dB; agents may give dB too:
  `"volume": {"db": -6}` or `"volume": "-6 dB"` on a track, bus, clip, line or the master. **Every plain-named
  instrument, modelled instrument, synth wave and drum kit is level-matched** (measured on three phrases each: a typical comp, bass, lead line, pad or groove as agents write it, the same notes
  at the Editor's velocity 0.8, and a held line of one note a bar; their mean comes out equally loud, so every one
  starts within about 3 LU of the others), and on top of that each starts at a rough-mix level: the recorded drum
  kits, the bass and the brass sit up to 2.5 dB under, strings 1 dB up. So tracks at the same volume are roughly
  balanced: a piano comp at 0 dB sits over the bass and drums at 0 dB. The master's gentle limiting keeps its limiter
  to 2 dB at most (it turns the whole mix down instead: guides/mixing-to-delivery.md). Roughly, not exactly: recorded
  instruments answer velocity very differently (string sections and brass get much louder when played hard), and a
  sound played outside its part (one loud chord on a glockenspiel) can be several dB off, so check with `look_sound` (`what: "levels"`) after the first render. How hard you play (`vel`) and how many notes you stack are still loudness: a five-note chord at vel 0.5
  is quieter than a bass note at 0.9. Sampled (SFZ) files you point at, plug-in instruments and recorded clips are not matched (their level is the file's).
- **The song's length** (`length`) is where it ends, a time: `bar(9)` is where bar 9 starts, so `length(bar(9))` is an
  8-bar song. For N bars write `length(bar(N+1))`. `run_script` and `inspect_item` (the song) end with the length in
  bars and seconds ("8 bars long (ends where bar 9 starts, 20.0 s)").
- **The song itself** is the item `"root"`: `{"op": "doc.set", "target": ["root"], "args": {"tempo": 96}}`. (`inspect_operations`
  lists item *types* in its target column; the ids come from `inspect_item`.)

## Which sound for which part

A plain instrument name (`builtIn`) plays a **recorded instrument**: piano, strings, bass, flute and the rest are real
recordings, not synthesized. Three names are analog synth presets (`warmPad`, `subBass`, `pluck`); `choirPad` is the older
synthesized choir (no free recorded choir exists); and every older synthesized voice is still there as `classic.<name>`
(`classic.feltPiano`, `classic.grandPiano`, `classic.warmPad`, `classic.analogStrings`, `classic.spiccatoStrings`,
`classic.choirPad`, `classic.cinematicBrass`, `classic.subBass`, `classic.glassMarimba`) for when you want that sound on
purpose. A name whose sample pack is not installed fails loudly and says how to install it (below). Each name has one part
it is made for and its level is matched on the first part listed. `inspect_engine` lists the same table (`roles`),
`inspect_engine (what "instrument") builtIn=… / model=… / synth=…` gives one sound's line and the range it was recorded
over: a note outside a recorded range thins out or is refused, so write inside it. Synthesized sounds play any key.

| Part | Plain names (`builtIn`) | Recorded range |
|---|---|---|
| comp (chords that keep time) | piano (grandPiano, acousticPiano, feltPiano), electricPiano (wurlitzer), guitar (nylonGuitar), acousticGuitar (steelGuitar), electricGuitar (cleanGuitar), harp, spiccatoStrings, organ | piano A0-C8, electric piano A1-C7, nylon guitar F1-B5, steel guitar A1-G6, electric guitar B1-D6, harp E1-F7, strings C1-D6 |
| bass (the low line) | bass (electricBass, bassGuitar), uprightBass (doubleBass), subBass (analog), basses, tuba, timpani | bass A0-G4, upright C1-C4, basses C1-C4, tuba F1-D4, timpani C2-C4, subBass E1-G3 |
| lead (a tune on top) | violin, cello, flute, piccolo, oboe, clarinet, saxophone (tenorSax), trumpet, mutedTrumpet (straight mute), marimba, vibraphone, xylophone, glockenspiel (keep it quiet), tubularBells (single strikes); `model` guitar / violin and `synth` triangle, sine | violin G3-C7, flute C4-C7, piccolo G4-G6, oboe A#3-F6, clarinet D3-F#6, sax G#2-F6, trumpet E3-C6, marimba F2-C#7, vibraphone F3-F6, xylophone G3-C#7, glockenspiel G4-C#7, bells C4-G5 |
| pad (held chords under everything) | strings (analogStrings: one section split by pitch into basses, cellos, violas, violins), violins, violas, cellos, brass (cinematicBrass), horn, trombone, pipeOrgan, organ, warmPad (pad), choirPad; `synth` saw, square | strings C1-D6, brass F1-C6, horn A1-F5, trombone A#1-F4, pipe organ C2-C#7, organ A1-D7, warmPad C2-C6, choirPad C3-C6 |
| groove (drums) | `kit`: drums (a recorded rock kit, the default), studio (a recorded studio kit), jazz (brushes, ride; a `stir` hit sweeps the snare), classic (synthesized) | the drum names under Notes in `inspect_guide script` |

Pianos, guitars, marimba, vibraphone and brass also play leads (`inspect_engine` lists every part each suits). Sampled (SFZ)
instruments you point at carry their own range (`inspect_engine (what "instrument") sfz=<path>`) and are not level-matched.

**Recorded or synthesized: which is which.** `inspect_engine` marks every instrument "recorded" or "synthesized" (read from the
engine's own instrument data). Recorded: every plain name except these. Synthesized: `warmPad` (alias `pad`), `subBass`, `pluck`,
`choirPad`, every `classic.<name>`, every `model=` instrument, every `synth=` wave and the `classic` kit. A name two forms share is two
different sounds: `builtIn="marimba"` (also `vibraphone`, `glockenspiel`) is the **recording**; `model="marimba"` is the **modelled** wooden
bar, synthesized, and `inspect_engine` lists it as `model:marimba`. **There is no recorded pad today**: the only pads are the synthesized
`warmPad` and `choirPad`. The closest recorded sustained sounds are `strings`, `violins`, `violas`, `cellos`, `organ`, `pipeOrgan`, `brass`,
`horn` and `vibraphone`; write them as held chords. There is no lo-fi instrument or noise bed either; the lo-fi tools are the `tape`,
`saturate` and `eq` effects (`inspect_guide 'script'`, "Effects and the master").

### Sample packs: install what a name needs

The recorded instruments are sample packs (large: the piano alone is 1.2 GB), installed on this machine, each file checked
by its fingerprint before it is kept. `inspect_library (kind: packs)` lists every pack, installed or missing, with its size,
licence and credit. A render, playback or audition that plays a name whose pack is missing stops and names the pack:
install it with `run_model_install` (`model: "salamander-piano"`, or `all-instruments`), or in a terminal
`python -m rostrum_sound.packs install salamander-piano` (`list` and `verify <pack>` are there too). Packs with a CC-BY
licence (the Salamander piano, the Wurlitzer, the rock kit) must be credited: a render that used them returns the credit
lines and writes them into the export's manifest.

### Feel: swing and played like a person (`perform`)

On the screen, a notes or drums track's settings have a **Feel** group. **Swing** makes every second 8th (or 16th)
come late; 100 % is a full triplet feel. It plays that way without moving the notes, so you can change it any time.
**Played like a person** adds the instrument's looseness, accents and strum; its amounts show under it. To write a
swing into the notes instead, use **Quantise ▾ › Swing**. Humanise writes the looseness into the notes, so you can see
and edit it; the track's Feel plays the notes loosely without changing them. Use one or the other on a part, not both.

Agents: `track.feel {swing: 0.55, swingGrid: 0.25}` changes only the values it names (a person's other settings stay);
`null` puts one back to the family's default; `{person: false}` turns the family's looseness off while swing still
plays. `track.set {perform: …}` replaces the whole object (use it only to write every value at once). In a script the same
operation is `t.feel(swing=0.55, swingGrid=0.25)`. `inspect_item` on the track ends with its feel ("Feel: swing 0.55 on
16ths."); `look_music beats` gives the swing set next to the swing heard.

Every instrument is played, not just sequenced. It is **on by default**: a track's notes get the timing feel, velocity
variety, accents, legato (sustained instruments), vibrato on held notes and strum of its family (plucked, mallets, drums,
sustained, detached, keys, synth); recorded clips, voice lines and audio are never performed. It is the same on every
render, because it is seeded by the track. The track field `perform` changes it: `perform=False` plays every note exactly
as written (use it for a part whose exact timing you wrote: a tight bass, a hit locked to a click, a MIDI import you want
as it is); `perform={"timing": 4, "velocity": 0.05}` changes some values over the family's defaults (`timing` ms, `lean` ms
behind the beat, `swing` 0…1 with `swingGrid`, `velocity` spread, `accent` 0…0.3, `strum` 0…1, `articulation` legato /
staccato / normal, `vibrato` {rateHz, depthCents} or false, `seed`, `person`: false = the family's defaults off, the
values named beside it still play). `humanize` and `phrase` in a script are different: they write values into your notes, while `perform`
leaves the notes as written and plays them differently.

## Notes are data

A note is `pitch` (MIDI number, 60 = middle C; the screen shows and takes names like G4), `at` (a time: seconds, `{"beat": n}` or `"#marker"`), `dur` (seconds
or `{"beats": n}`; note the plural), `vel` (0..1), plus the instrument's own playing settings when they apply (an articulation `art`
on an articulated SFZ, `position` / `damping` on a plucked string, `bend`, `vibrato` …). Only the settings the track's
instrument can use are offered (the screen hides the rest). On the screen a note's At and Length read in bars.beats (At **5.3** = bar 5, beat 3; Length reads as a note value when it is one: **1/8**, **1/4**, **dotted 1/4** … , else words (**1 beat**, **2 bars 1 beat**); hover it for the seconds) and take `5.3`, `1/8` or `1 bar 2 beats` (a length), `9.6 s` or `0:09.6` typed (the old `0.2` and `5.3.480` still work); the file keeps the form it had. Drum tracks use hits (`hit.add`: `drum`, `at`, `vel`).

- One note: `note.add`. Many in one undo step: `note.add_many` with `notes`. Change: `note.set`. Remove: `note.remove`.

## On the screen

- **A new track** starts from a sound in the **Library** (Ctrl+L): every row has its own **Add**, and Add always makes a new
  track. To change a track's sound, pick another in the **Sound ▾** field of its settings panel (the notes stay).
- **Editor** (the dock under the arrangement, E; the selected track): it opens tall (about three quarters of the room under the arrangement) and centred on the track's notes the first time. Every key row has one height (12 px), whatever the track holds, and each track comes back where you left it (scrolled up or down) when you open the Editor again, undo, come back from another track, or close the song and open it again (the zoom and the bars in view come back too, and so do the open Editor or Mixer at the height you dragged it, the Grid, Note ▾'s length and what Draw stamps), so a click lands on the key and the bar you were looking at. When the whole song is in view it opens on about 8 bars from the bar before the selected notes (or the playhead), so the grid cells are wide enough to aim at; Fit (Ctrl+0) shows the music again. It sits beside a
  piano keyboard (a C label on every octave; click a key to hear it on the track's instrument). Its top line, beside
  the Editor / Mixer tabs, holds the track's name, **Select** (V) / **Draw** (B) and **Note ▾** (how long a new note
  is, and under Draw whether a click stamps a single note or a chord). Double-click to add, or the **Draw** tool where every click adds, in the grid cell under the pointer (a click on a grid line goes in the cell after it), or on a marker within a few pixels of it. With Draw, a faint note (or hit; with a chord chosen in Note ▾ › Draw, every note of the chord) shows where a click would put it, at the length it would get, and its key lights on the keyboard; a hit a click would remove lights red, and so does a note while you hold Alt (the pointer changes as soon as you press Alt, no need to move) (Draw+Alt click erases that note; Draw+Alt drag still copies). The pointer says what a press does: the arrow on a note (a + badge while you hold Alt: the drag copies; a closed hand while it moves), a sideways resize arrow on its ends (a chip by the pointer says the length, "1/8"), a crosshair where Draw adds, the arrow with a red − where Draw removes; in the velocity strip, an up-down arrow on a bar and a crosshair on empty space (draw a line). While you move notes a chip by the pointer says how far ("+1 bar 2 beats · +3 semitones"); Esc during any drag puts everything back as it was, with no undo step; drag to move (it snaps to a marker or section edge within a few pixels, else to the grid set by **Grid ▾**, with **Snap** on; Ctrl = no snapping,
  Alt = a copy, Shift = only in time), drag its right end to lengthen or shorten it, its left end to move its start (the end
  stays; neither makes it shorter than one grid step), Delete removes. A note dragged towards the end of a song of a set
  length stops on the last grid line before the end. Each drag
  is one undo step (a note drawn with the Draw tool, dragged long, too: "Draw note"); the new note is selected. Clicks in the roll never move the playhead and the view never scrolls by itself. Drum tracks show a row per drum, a hit as a diamond on its time (it is caught only on the diamond itself: a click on the empty step beside it adds there, and erasing a hit never touches the step next to it); **+ Drum ▾** on the top line adds a row for any other drum of the kit, and a hit's **Drum** field in the settings panel is a picker of the kit's drums. Select several (Ctrl+click, Shift+click, a box) and act on them
  from the top of the settings panel, the right-click menu (Cut, Copy, Duplicate, Delete, then Quantise, Humanise,
  Transpose ▸) or keys: Q quantise, Ctrl+D duplicate, ↑ / ↓ a half step. After Ctrl+V or Ctrl+D the roll slides just far enough to show the new notes (not at all when you can already see them) and they flash once; a copy (Ctrl+C) is kept even after you close Rostrum, so Ctrl+V pastes it the next time too. Right-click on empty roll space offers Add note
  here, Paste here (in the grid cell under the pointer), Select all on this track and Select every C4 (the key you
  clicked); right-click on the roll's ruler: Add marker here, Make a section from here, Show seconds.
- **A note's own playing** (in its settings panel under **More**): **Swell** (its level across its length, 1 = as played:
  `0.8` for all of it, `0.5 → 1.5` for a swell, `0.5 → 1.2 → 0.8` spread evenly), **Vibrato** (`30` = 30 cents at 5.5 Hz;
  `40 · 6 Hz · after 0.2 s`; `off`) and **Bend** in cents (`-100` bends the whole note down a half step, `0 → 200` slides
  up a whole step across it; `0` = none). The **Pitch** field takes a name (`C5`), a MIDI number (`72`) or a chord
  (`60 64 67`).
- **Velocity strip** (at the bottom of the Editor; ▾ Velocity at its bottom left folds it to one line, staying where you clicked): one bar per note, as high as it plays loud. Drag a bar, or draw a line
  across several: the line sets the selected notes when some are, else every note under it, and says which beside it
  while you draw ("Velocity 80 %", with "every note" or "the selected note" under it). The value of the bar under the pointer (or of the selected
  notes) is written beside it ("70 %").
- **Playing lane** (between the notes and the velocity strip, for an instrument that plays notes; folded to one line "› Sustain · Expression · Bend" while the track has none of them: click it to open: it opens upward, the notes giving the room): the picker at its head (it names the lane, "Sustain ▾") chooses **Sustain** (the pedal: up
  at the bottom, down at the top; a note let go while it is down rings on until it lifts), **Expression** (how loud
  the whole part plays, like a swell on the strings) or **Bend** (the pitch wheel: the middle is no bend, the top
  and bottom are up and down by the track's **Bend range**, 2 semitones unless you change it in the settings panel).
  Click to add a point, drag it, Delete removes it (or right-click it: **Delete point**); ← / → move the selected point
  a grid step, ↑ / ↓ a twentieth of the lane's height (Shift: five times as far); one drag is one undo step. It is the same lane as the track's
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
- A lane's points must be in time order (`sustain points are not in time order` is refused, naming the point): write them from
  first to last, a step as two points at one time. Agents set the lanes with `automation.set` on the track: lane `sustain` (0 up … 1 down), `dynamics` (expression,
  0 … 2, 1 = as played), `bend` (-1 … 1 × `bendRange` semitones, `track.set {bendRange}`: a track with no bend lane yet takes it only in the
  same call as the lane, in either order); a step is two points at
  one time. In a script: `t.sustain([...])`, `t.dynamics([...])`, `t.bend([...], range=2)` (see `script`).

## From a script

`run_script` builds tracks and notes in Python. Re-running a script merges: notes a person moved by hand stay where
they were put and are listed as held back. Helpers write plain values you can edit afterwards, e.g. seeded
`humanize(seed, timing, velocity)` for small timing and velocity variation (see `script`). The operation for
notes already written is `note.humanize`, with note ids as its targets (not the track):
`{"timing": 15, "velocity": 0.08, "length": 0.1, "seed": 2}` (`length` 0 … 0.5: how much each note's length may vary,
notes only; the same seed on the same notes gives the same result every time). It moves each note from where it is now, so it **stacks**: on a script's own `humanize` (the script's offsets are already in the notes), and on an earlier `note.humanize` (the same seed adds the same amount again). Humanize a part once, or undo and run it again with other amounts. `hit.humanize` is the same for drum hits (`timing`, `velocity`, `seed`). The track's Feel (`track.feel`) is another kind: it plays the notes loosely without changing them.

## Operations on notes already written

These edit notes that exist (a person's, or an earlier script's); to write a new part, use the script helpers (`writing-music-tools`). Every one runs
through `edit_document` (`ops`, a list of `{op, target, args}`; whole calls to copy are in `start-here`). Name the notes by id, or with a range
target `{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}`: every note of that track starting from bar 1 up to (not including) bar 9; the
same for hits. Example, a fifth up on those bars: `{"ops": [{"op": "note.transpose", "target": [{"track": "guitar", "from": {"bar": 1}, "to": {"bar": 9}}], "args": {"semitones": 7}}]}`.

- **Repeat:** `note.duplicate {times: 4}` repeats a bar four times (each copy right after the last; `by` sets another
  step, `{"beats": 32}` for 32 beats); `{until: "#chorus"}` fills up to the chorus marker, `{until: {"section": "verse"}}` up to the end of the verse
  section, `until` a time in seconds or beats as well. The last copy is cut at that point and never crosses it (notes and
  clips shortened, hits past it left out). The same on `hit.duplicate` and `clip.duplicate`; one call is one undo step.
- **Transpose:** `note.transpose {semitones: 7}` moves notes up a fifth in half steps; `note.transpose {steps: 2}` moves
  them two steps of the song's key (a third), each note in the key at its own time, a chord by its lowest note's step.
  Give one of the two. Without a key, `steps` fails ("The song has no key …"); a note that would leave the 128 MIDI keys (0 to 127) fails the whole call and changes nothing. There is no limit on how
  many notes one call moves (a whole track, or a range target, in one call: no chunking).
- **Thin:** `note.thin {keep_every: 2}` keeps every other note of each track (time order; `offset: 1` keeps the other
  half) and removes the rest; `note.thin {below_vel: 0.3}` removes the notes played softer than that. Give exactly one of
  the two. The same on `hit.thin`. Works on ids and on a range target, one undo step.
- **What the reply says:** every `edit_document` answer lists what changed, counts per kind and the first 12 ids, each as
  `id at <seconds> s <pitch> <length>` (a hit: its drum; a clip: its range), in the sentence after "Applied …" and in
  `changed.items` (`added`, `changed`, `removed`, each with `count`, `types`, `ids`, `items`, `more`). A thin or delete also says
  "Kept K of the N targeted". A note's id is the track and where it started, in milliseconds, when it was made (`harp.n8438`); it
  stays when the note moves or the tempo changes (a script run again at a new tempo keeps each note's id, and the edits a
  person made to it), so read times from `inspect_notes`, never from ids.
- **Arpeggiate** keeps every tone of the chord: a chord too short for one step per tone gets finer steps than `rate`
  (3 tones in one beat at rate 0.5 play as thirds of a beat), never a dropped tone.
- **Fit to key:** `note.fit_key {}` moves the notes that are outside the key to the nearest note of the key (the song's
  key at each note's own time; `key: "D minor"` to name one; `direction: "down"` or `"up"` to always go one way; with
  "nearest", a note halfway between two notes of the key goes up: C#4 in D minor becomes D4). Notes already in the key
  are not touched, a chord is fitted tone by tone, and it is one undo step. Without a key (and no `key` given) it
  fails. Find the wrong notes first with `inspect_harmony`.
- **Which notes are a chord** (for invert, strum and arpeggiate): selected notes on one track that start within 30 ms
  of each other, or a strummed chord (each note starting at most 200 ms after the one before and ending where another
  note of the chord ends, within 10 ms); a note whose pitch is a list is a chord on its own.
- **Make a chord:** `note.chord {shape: "key"}` builds a chord on each selected note by adding its other tones as
  separate notes (same start, length and velocity), so each can be edited. `"key"` is the key's own chord on that
  note (D in C major gives D–F–A, B gives B–D–F), `"key7"` adds its 7th; both need the song's key and a note that is in
  it. Named shapes: `"major"`, `"minor"`, `"sus2"`, `"sus4"`, `"power"` (root and 5th), `"octave"`. `inversion: 1`
  (2, 3) puts the chord's 3rd (5th, 7th) lowest; the selected note stays where it is. Tones already sounding there are
  not added twice. One undo removes the added tones only. For finer voicings (drop 2, spread, voice leading) write
  the chords in a script with `voice(...)` (`inspect_guide 'writing-music-tools'`).
- **Invert:** `note.invert {by: 1}` moves each chord's lowest note up an octave (`-1`: the top note down; `±2`, `±3`
  repeat it). A list chord turns inside its list. A tone outside the 128 MIDI keys (0 to 127) fails it and changes nothing.
- **Strum:** `note.strum {gap: 30, soften: 0.1}` makes each note of a chord start `gap` ms after the one below it
  (`gap: -30`: from the top note, an up-strum) and keeps each note's end, so the later notes get shorter. `soften`
  makes the last note that much softer than the first (0.1 = 10 %), the ones between in steps. Strumming a strummed
  chord re-spaces it from its earliest start, so it never stacks; `gap: 0` lines the chord up again. A list chord gets
  its own `strum` field instead. It fails if a note would start at or after its end (a shorter gap, or longer notes).
- **Arpeggiate:** `note.arpeggiate {rate: 0.25, mode: "up", octaves: 1, gate: 0.9, seed: 1}` replaces each chord with
  its notes one after another over the chord's own length: a step every `rate` beats (1/32 … 1), in `mode` order
  (`up`, `down`, `upDown`, `downUp`, `converge`, `diverge`, `order` = as written, `random` = the same every time for
  one `seed`), over `octaves` octaves (1 … 4), each note holding `gate` of its step. Every new note lies inside the
  chord's span and copies the velocity of the chord note it plays; one undo brings the chord back.
- **Fill a drum row:** `hit.fill` on the drum TRACK as the target (`"target": ["drums"]`), args `{drum: "hat", every: 0.5, offset: 0, from: {"beat": 0}, to: {"beat": 4}, vel: 0.85}`
  adds hits of one drum every `every` beats (1/32 … 32) from `from` up to (not including) `to`, the first one `offset`
  beats after `from`; `accentEvery: 2, accentVel: 1` makes every second beat an accent. It adds only where that drum has no
  hit within 10 ms, so it never doubles a hit and never moves one, and it is one undo step. The drum must be one the
  track's kit plays. Off-beats are `every: 1, offset: 0.5`. To clear a drum, call `hit.remove` on its hits. In a
  script, `drum_grid(...)` makes the same hits from step strings.
- **Quantise with swing:** `hit.quantize {grid: 0.5, swing: 0.6}` writes a swing into the hits: the off-beat grid lines
  move late (1 = a triplet feel) and the hits snap to them. To swing without moving the notes, use the track's feel
  (below).

## Checking the part

- `look_music` (`what: "harmony"`) (`track` optional): the key, the chord per bar or beat, and plain facts about the written notes:
  notes outside the instrument's range, voices crossing, close intervals low down, notes out of key. Chord and note names
  are spelled for the key (flats in flat keys).
- `look_music` (`what: "pitch"`) with `track` after a render: every written note (each note of a chord too) judged on
  its attack, so ringing notes, pedal and reverb never count against it: ok, wrong octave, missing; on a one-voice part
  also late, early, out of tune, wrong note. The first line says the track's register in plain words ("bass sounds
  where written", or "sounds one octave lower than written on N of M notes: the instrument's samples, or your octave").
- `look_music` (`what: "beats"`): whether the played notes sit on the grid, per onset in ms.

These report facts; whether a line is musical is decided by listening.
