# The Sound script API (run_script)

A script describes the whole song; `run_script` merges it into the document. Run the same script again after a
change and only what the script changed moves: anything a person changed by hand is kept and listed as held back,
saying who got there first ("already changed by agent:mcp (\"Run map.py\")"; pass `force` with the ids to take over).
**The script's `name` decides replace or add:** the same name replaces and merges what that script made; a new name adds
a second copy beside it (the reply warns). Keep one script name per song, and to change what an earlier script made, run
under its name; a check that fails because two scripts made the same things names the earlier script. A script error names the script and line; an unknown track method lists what a track
can do, an unknown name lists the script's names. **A run that fails changes nothing** (no half-made track is left): fix
the line it names and run again. A run that merged says so, even when a note ends before it starts (a warning naming
the note, see "Before the render"). Times can name the song's markers (`"#drop"`,
made with `marker.add`) and the project's without the script restating them.

**The call.** `run_script` takes `source` (the Python text, required), `name` (the script's name, default `agent_script.py`),
`item` (the song, when more than one is open), `force` and `detail`. There is no `script` or `code` argument.

```json
{"tool": "run_script", "arguments": {"name": "cue", "source": "tempo(96); length(bar(9))
t = track('keys', builtIn='piano')
t.note('D4', at=bar(1), dur=beats(4))"}}
```

**Names.** A track, section or other item id is 1 to 64 letters, digits, `_`, `.` or `-`: `"final_chorus"`, never `"final chorus"`
(a track called `"guitar lead"` fails the same way). Marker names are free text and may hold spaces (`marker("logo lands", at=...)`,
used as `"#logo lands"`). The song's item is `cue` unless `inspect_project` says another.

The writing helpers (voicings, bass lines, arpeggios, fills, sections) that work inside a script are in inspect_guide 'writing-music-tools'.

```python
tempo(96); length(bar(9)); beats_per_bar(4)              # 8 bars: bar(n) is where bar n starts, length is where it ends
marker("drop", at=bar(5))                                 # name a moment; other times can say "#drop" or "#drop+0.5"
s = track("strings", sfz=r"C:\...\Violins.sfz", volume=0.8)   # instrument from sfz= / builtIn= / kit= / kitSfz=; builtIn="piano" is a recorded piano
s.note("D4", at=beat(0), dur=beats(4), vel=0.7)
s.chord(["D3", "A3", "F4"], at="#drop", dur=beats(2))
s.note("A4", at="#drop+5", end="#end")                    # ends ON the marker "end" (a note can end on a time or a marker)
d = track("drums", kit="drums"); d.hit("kick", at=beat(0)); d.hit("snare", at="#drop+0.5")   # drums: see Notes
v = track("door"); v.clip(r"C:\...\door.wav", at=3.0, in_=0.42, length=1.2)
s.effect("reverb", space="hall", mix=0.3)
s.automate("volume", [(0, 0.2), ("#drop", 0.9)])
master(loudness=-16, truePeak=-1)                         # a loudness target turns normalize on; the ceiling is held
for i in range(8):
    s.note("A4", at=bar(2) + i * beats(0.5), dur=beats(0.5))   # beat arithmetic: a time + a length is a time
```

**The song's length is where it ends, a time.** `bar(1)` is the start of the song and `bar(n)` is where bar n starts,
so `length(bar(9))` is an 8-bar song: for N bars write `length(bar(N+1))`. The reply of every `run_script` ends with
the length worked out ("Song: 96 bpm, 4/4; 8 bars long (ends where bar 9 starts, 20.0 s)"), as does `inspect_item`
on the song.

Check what you wrote before rendering: `look_arrangement` draws every track's notes and hits with the bars, sections
and markers, and says which tracks start on each marker.

## Effects and the master: every setting, with its unit

`s.effect(type, **settings)` adds an effect to a track (`inspect_operations` `effect.add` / `effect.set` take the same
names). Every number is a plain number in the unit below, never `{"db": ...}` and never milliseconds. The full list, with
defaults and ranges, is what `inspect_engine` returns (`data.effects`, `data.master`): it is read from the same table the
checks use, so it cannot disagree with them. A setting marked "curve" also takes a list of `[time, value]` points.

| Effect | Settings (unit) |
|---|---|
| `compressor` | `threshold` dB (-80 to 0), `ratio` :1 (1 to 30), `attack` seconds (0.0001 to 1), `release` seconds (0.001 to 5), `makeup` dB, `knee` dB |
| `eq` | `bands`: a list of `{shape, freq (Hz), gain (dB), q}`; shapes `lowshelf`, `highshelf`, `peak`, `lowpass`, `highpass`, `notch` |
| `reverb` | `space` (below), `mix` 0 to 1, and with a `freeverb.*` space `decay` seconds, `damping`, `size` |
| `delay` | `time` seconds, `feedback` 0 to 0.98, `mix`, `pingPong` true/false, `damp` |
| `saturate` | `drive` 0 to 1, `mix` |
| `tape` | `wow`, `flutter`, `age`, each 0 to 1 (`wow` a slow pitch drift of up to about 15 cents, `flutter` a fast waver, `age` adds saturation and a darker, thinner tone) |
| `limiter` | `ceiling` dB, `release` seconds |
| `width` | `width` 0 to 2 (1 = unchanged), `monoBelow` Hz |
| `gate` | `threshold` dB, `ratio`, `range` dB, `attack` / `hold` / `release` seconds |
| `deess`, `dehum` | see `inspect_engine` |

Reverb spaces: `dry`, `room`, `hall`, `cathedral`, `shimmer`, and the adjustable `freeverb.room`, `freeverb.hall`,
`freeverb.cathedral`. Tones (`tone=` on a track): `neutral`, `muffled`, `warm`, `sub-boost`, `bright`, `voice-clarity`, `radio`.

```python
s.effect("compressor", threshold=-24, ratio=4, attack=0.01, release=0.2)   # dB, :1, seconds
s.effect("tape", wow=0.3, flutter=0.2, age=0.5)
master(loudness=-14, truePeak=-1, glue=0.2, fadeOut=1.8)
```

`master(...)` takes `volume` (gain 0 to 4), `normalize`, `loudness` (LUFS, -60 to 0: giving it turns `normalize` on),
`truePeak` (dBTP, -12 to 0), `gentle` (on by default) and `maxLimit` (dB, 0 to 12, default 2: with `gentle` on, the
limiter never pulls the loudest moment down by more than this; a mix that would need more is turned down as a whole,
so it lands under its loudness target and `render_mix` says by how much; `edit_loudness` is the one call that fixes it), `glue` (0 to 1), `reverb` and `trackReverbSpace` (spaces), `fadeIn` and `fadeOut` (seconds, 0 to 600) and
`safetyClip`.

There is no vinyl-crackle or bit-crush effect, and no noise-bed sound. For a worn, lo-fi sound the tools that exist are
`tape` (wow, flutter, age), `saturate` (drive), an `eq` low-pass (`lowpass`) and high-pass, a `reverb`, a `delay`, and the
performance layer's swing and lean (below).

**Tape settings.** All three run 0 to 1 and default 0.2. `wow` is a slow pitch drift (up to about 15 cents at 1; the
"seasick" one), `flutter` a fast waver, `age` adds saturation and a darker, thinner tone. For a gentle worn sound stay
under about 0.4 on `wow` and `flutter`; the number a look tool reports (`look_music pitch`: drift and vibrato per note)
shows what it did, whether it is pleasant is for a person to hear.

**Lo-fi, as techniques** (settings to start from, not a finished piece; move each to taste and check with the look tools):

- *Dull the top:* an `eq` band `{"shape": "lowpass", "freq": 3500 to 6000, "q": 0.7}` on keys, vibes and the drums, so
  nothing sparkles; a `highpass` near 60 to 80 Hz on the keys so they leave the bass room.
- *Warble and wear:* `tape` on the keys and the lead, `wow` 0.2 to 0.4, `flutter` about 0.2, `age` 0.4 to 0.7; not on the
  bass or kick, where pitch drift reads as out of tune.
- *Grit:* `saturate` with `drive` 0.2 to 0.5 on the drums and the bass; a compressor with a slow `release` (0.2 to 0.4 s)
  on the drums holds the hits together.
- *Laid back:* `perform={"swing": 0.3 to 0.6, "lean": 5 to 15}` on the drums and keys (see "Swing" below); keep the notes on the grid.
- *Space:* a small `room` reverb with a low `mix` and a dark `delay` (`damp` 0.5 or more) on the lead, not on the bass.
- *What is missing:* crackle, hiss and bit-crush do not exist; a recorded sound you add as a clip (`inspect_library`) is the
  only way to get a noise bed, and the sound must be one you may use.

## Ending a song

A song stops at its `length`. What a clean end needs, with what exists today:

- **Let it ring.** A note ends where you wrote it, and the instrument's own release and any reverb ring on after it. With
  **Ring out** (the song field `ringOut`, on in every new song) a sound still ringing at `length` plays on until it dies away
  (under -60 dBFS, at most 6 s more) and the file ends there; a note held past `length` is let go at it, and a note that starts
  at or after `length` is not heard (both are warned, in `run_script` and `render_mix`). `length` is where the music stops,
  not where the file stops: `length(bar(21))` after a chord let go at bar 21 rings it out. Songs saved before 2026-10-25 open
  with Ring out off (they sound as they did): there the file stops at `length`, so leave the tail room yourself.
- **Check the end.** `look_sound` (`what: "loudness"`) answers an `ending` line from the render: the level of the last 0.5 s,
  whether that is still above -50 dBFS, and whether the last 50 ms drop faster than the fade before it. Still above -50 dBFS
  with a fast last-50-ms drop is a cut: the file stops while the sound is still ringing. The fix is `ringOut` on, a later
  `length`, or `master(fadeOut=...)`. The render also answers `ending` (`length`, the file's `end`, `levelAtLengthDb`, `cut`)
  and a warning when the ending is cut.
- **Soft end.** Only with Ring out off; on by default (the song field `endFade`): anything sounding at `length` is faded over
  its last 0.1 s so the file never ends on a click. It does not make a ring-out natural; it only removes the click. `inspect_diagnose` reports `hard-end`
  if it is off and sound still plays.
- **Fade out.** `master(fadeOut=1.8)` fades the whole mix to silence over the last 1.8 seconds before `length` (so keep `length`
  where you want silence). On a held chord at the very end a 1.5 s fade measured: the last half second at -56 dB instead of -21 dB.
- **`trim`.** `render_mix` trims the end only where the sound is below -80 dBFS; the reply says `trimmed: false` when sound above
  that runs to the end (a long ring, a reverb tail). Trim removes silence; it does not fade anything. Pass `trim: false` to keep the
  full `length`.

## Playing: instruments, articulations, expression

```python
g = track("gtr", model="guitar", position=0.2, damping=0.3)   # guitar, nylonGuitar, marimba, vibraphone,
                                                              # glockenspiel, tubularBell, violin
pad = track("pad", synth="saw", attack=1.2, brightness=1800)  # saw, square, triangle, sine (+ release, voices …)
vln = track("vln", sfz=r"C:\...\ViolinSus.sfz", legato=True, swell=True,
            articulations={"spiccato": r"C:\...\ViolinSpic.sfz", "tremolo": r"C:\...\ViolinTrem.sfz"})
vln.note("D5", at=bar(3), dur=beats(4), dynamics=[(0, 0.6), (1, 1.0)], vibrato={"rate": 5, "depth": 20, "delay": 0.3})
vln.note("A4", at=beat(2), dur=beats(0.5), art="spiccato")    # a named articulation; none = the main file
g.note("E3", at=0, dur=1, position=0.4, bend=[(0, -100), (0.08, 0)])   # this note's touch; a scoop up
vln.dynamics([(bar(13), 0.5), (bar(17), 1.3)])     # CC 11 over the track (0 … 2, multiplies every note)
vln.vibrato([(0, 0), (bar(3), 0.6)], rate=5.5, depth=25)   # mod wheel 0 … 1 (1 = depth cents at rate Hz)
vln.bend([(bar(5), -0.25), (bar(5) + beats(1), 0)], range=2)  # pitch wheel -1 … 1 (× range semitones, 2 unless set)
keys = track("keys", builtIn="piano")      # perform=False plays every note exactly as written (guide: writing-parts)
keys.sustain([(0, 0), (bar(2), 0), (bar(2), 1), (bar(3), 1), (bar(3), 0)])   # pedal CC 64: down bars 2–3 (steps)
vln.phrase(bar(5), bar(9), vel=[(0, 0.5), (1, 0.9)])  # velocity along the phrase, for notes that wrote no vel
f = vel_curve([(0, 0.5), (1, 0.9)], bar(5), bar(9)); vln.note("D4", at=bar(6), dur=1, vel=f(bar(6)) + 0.15)
vln.humanize(seed=3, timing=0.012, velocity=0.06)   # every note / hit on the track, ±12 ms, ±0.06
```

- `legato`: overlapping notes glide as one line (write each note slightly longer than its gap). `swell`: long
  notes swell in. Both are per track, and **only for a track made from an `sfz` file** (`sfz=...`): on `builtIn`, `model`,
  `synth`, kit or `plugin` tracks the call is refused with `"legato" only applies when Instrument is "sfz"`, so a recorded
  `builtIn="violins"` cannot take it. A recorded builtIn sustained instrument (strings, brass, winds, organ) already
  slurs overlapping notes through the performance layer; to ask for it explicitly on any track write
  `perform={"articulation": "legato"}` (holds each note into the next).
- **Swing.** `perform={"swing": 0.5}` delays the off-beat notes: with the default `swingGrid` 0.5 (eighth notes) every second
  eighth comes late by `swing` x one sixth of a beat (swing 1 is a triplet feel, 2:1; 0.5 halfway there, a light
  shuffle, 58 ms late at 85 bpm); `swingGrid` 0.25 swings the sixteenths instead. A note is moved only if it is written on that
  grid (within 8 percent of a cell), so write the notes straight and let `swing` move them. `lean` (ms, + behind the beat) and
  `timing` (ms, random) are separate. A track can also call the document's own `track.feel`, which changes only what it
  names: `d.feel(swing=0.55, swingGrid=0.25)` (any `track.<op>` that changes only the track's own settings is a method
  the same way; one that changes notes or other items, like `track.duplicate`, says to use `edit_document` after the
  script). Check it: `look_music beats` says "swing set 0.55 on 16ths (drums), heard 0.56" (heard on the same scale;
  the offsets are measured against the swung grid, so swung off-beats are on time, not late).
- Touch fields (`position`, `damping`, `hardness`) are a model track's defaults; a note may override them.
  `damping` is plucked strings only; `position` / `hardness` not for violin. Wrong ones fail with the reason.
- `humanize` and `phrase` write plain numbers into the notes when the script runs. Offsets come from the seed and
  each note's id (made from its written time), so a re-run gives the same values and keeps a person's edit;
  another seed gives another draw. The `dynamics` / `vibrato` / `sustain` / `bend` lanes are the same
  `automation.set` operation as volume / pan (lane `dynamics` / `vibrato` / `sustain` / `bend`); the screen calls
  `dynamics` "Expression" and shows Sustain, Expression and Bend under the Editor's velocity strip. A note let go
  while the pedal is down (0.5 or more) rings on until it lifts; a bend lane moves every note on the track (put a
  line that should stay in tune on its own track) and adds to a note's own `bend`.

## Editing recorded sounds: stretch, shift, layers, plug-ins

```python
d = track("door")
d.clip(r"C:\...\slam.wav", at=3.0, stretch=1.5, shift=-3, fadeOut=0.2)   # 1.5× longer, 3 semitones down, same pitch / same length
d.layer("door", [r"C:\...\thud.wav", {"media": r"C:\...\creak.wav", "volume": 0.4, "at": 3.1}], at=3.0)
d.clip(r"C:\...\latch.wav", at=3.4, group="door")                          # the same thing, one clip at a time
d.effect("plugin", plugin={"format": "clap", "path": r"C:\...\Tape.clap", "id": "org.x.tape", "name": "Tape",
                           "params": {"drive": 0.4, "mix": [(0, 0), (bar(5), 1)]}})   # a list = that setting's lane
synth = track("lead", instrument="plugin", plugin={"format": "vst3", "path": r"C:\...\Synth.vst3", "id": "…"})
```

- `pitch` is tape-style (pitch and speed together); `shift` changes pitch only, `stretch` speed only (a clip lasts
  `length × stretch`). Use both for a re-pitched sound at its own length.
- **Layers are a name, not a list.** Clips of one track with the same `group` are one sound. `clip.set` on one of
  them moves the others with it (`at`, each keeping its own timing form: seconds, beats, a marker) and scales their
  `volume` by the same factor; the layer stops at the start of the mix. `clip.set_one` changes only that clip, to
  balance a layer inside its group. `clip.remove` and every other field stay per clip. One call = one undo step.
- A plug-in is one `plugin` record: `{format: "clap"|"vst3", path, id, name?, params?, state?}`. `params` holds the
  settings you changed, `{param id: number or [[time, value], …]}`; a list is that setting's automation lane
  (`param:<id>`). `inspect_engine` (`what: "plugins"`) lists what is installed with each setting's id, range and default. `state` is
  what the plug-in's own window saved (the Mixer's "Open window" writes it). We bundle no plug-ins.

## The song's map: tempo changes, key, sections, MIDI

```python
tempo(96)                                   # the starting tempo
tempo_change(bar(9), 132)                   # from bar 9 on (a beat: it stays on its beat), until the next change
tempo_change(42.0, 100)                     # or at seconds: it stays at that moment
tempo_change(bar(25), 90, ramp=True)        # glides from 90 to the next change's tempo (an accelerando), exact
tempo_change(bar(33), 120)                  #   per beat, not in steps; this one then holds 120
meter_change(bar(17), 3)                    # 3 beats a bar from bar 17 on (a new bar starts there), until the next
meter_change(bar(18), 4)                    #   change: one 3/4 bar. bar(n) counts them, so change before using later bars
key("D minor"); key("F major", at=bar(17))  # the key from a time on ("F# major", "Bb dorian" …): data, not heard
section("intro", bar(1), bar(5)); section("drop", bar(9), bar(17))
tracks = import_midi(r"C:\...\sketch.mid")  # its tracks, markers, sections, tempo map and keys; returns the tracks
tracks[0].set(instrument="sfz", sfz=r"C:\...\Cello.sfz")
```

- **One tempo map.** Every beat time (`beat(n)`, `bar(n)`, `beats(n)`) goes through the tempo map: the doc's `tempo`
  to the first change, then each change's bpm (a change with `ramp=True` glides evenly to the next one's). The screen's ruler, the ids,
  the checks and the engine's render all read the same map. A tempo change can't sit on a marker.
- **What follows a tempo change:** things written in beats stay on their beat (they move in seconds); things in
  seconds stay at their moment (their beat moves). Markers follow the same rule: a marker at `bar(5)` stays on bar 5,
  a marker at `12.0` stays at 12 s. Write in beats what belongs to the music, in seconds what belongs to the picture.
- **Moving a section:** `edit_document` `{"op": "section.move", "target": ["section.drop"], "args": {"by": {"beats": 8}}}`
  (or `"by": -2.5` seconds) moves the section and everything that starts inside it (notes, hits, clips, voice
  lines, tempo and key changes, other sections, automation points) in one undo step. **Markers stay** (they are
  sync points: a picture cut, "logo lands"), and so do the song's opening tempo, time signature and key; add
  `"markers": true` to move the song's own markers inside the section too. Each time keeps its form; a time on a
  marker that stays keeps the marker with a new offset. Effect envelopes inside effects don't move.
  A time signature change must stay on a bar line, so a section holding one moves by whole bars only (a move that
  puts it off a bar line is refused and names the nearest bar lines). In the arrangement: drag the section's bar (Ctrl = off the grid);
  it carries what was inside it when you pressed, never what it passes over, and lets go as one `section.move`.
- **Keys** are for you and the screen (the readout shows the key at the playhead): `doc/keys.py` has `scale`,
  `in_key`, `snap` (nearest note of the key). They change nothing in the sound.
- **MIDI:** `edit_import_midi` `{path, song_map}` imports a .mid as one undo step (channel 10 becomes drum hits on
  the drum kit; other channels a plain recorded instrument picked from the GM program, to change after); `render_mix` (`what: "midi"`)
  writes the document's notes, hits, sustain / expression / mod wheel / bend lanes (CC 64, CC 11, CC 1, the pitch
  wheel, bend range as RPN 0; import reads them back), tempo map, time signature, keys, markers and sections (as
  cue points) to `renders/<item>/midi/<item>.mid` (the screen: Export › What for › MIDI file). What MIDI can't carry comes back as a warning. Clips and
  voice lines are audio and are not written.
- **A MIDI keyboard** (screen): arm a track, "Record keys" (shown only with a keyboard connected) records while the
  mix plays; Stop puts the take on the armed track in beats, one undo step. The sound you hear while playing is a
  monitor (an SFZ track plays its file, others a plain synth); the render plays the track's instrument.

## Notes

- Times: seconds (`2.5`), `beat(n)` (from the start, 0-based), `bar(n)` (1-based), or a marker (`"#drop"`; a name
  with spaces works as written: `"#logo lands"`, `"#logo lands+0.5"`, `"#logo lands" + beats(2)`). Lengths: seconds or `beats(n)`;
  a note's length may also be `end=` a time or marker, or `"next"`.
- **Beat arithmetic:** a time plus or minus a length is a time (`bar(5) + beats(2)`, `beat(i * 4) - beats(0.5)`), two
  times give the length between them (`bar(9) - bar(5)`), lengths add and scale (`beats(1) * 3`, `i * beats(0.5)`),
  and times compare with times (`bar(5) < bar(9)`); adding 0 changes nothing. Any other bare number is seconds, so `bar(5) + 0.5` or `bar(5) < 3.0`
  is refused, naming the forms to write instead (`bar(5) + beats(0.5)`, or `t["beat"]` for the beat number itself).
  A marker plus beats is a time on that marker (`"#drop" + beats(2)`); seconds after it are `"#drop+0.5"` (not both).
- **End on a marker, not on a number.** `end=` instead of `dur=` ties a note's end to a time or a marker:
  `s.note("A4", at="#drop+5", end="#end")` (same as `dur=until("#end")`), `end="#end" - beats(1)` one beat before it,
  `end="#end" + beats(2)` two beats after it (a section too: `section("outro", "#drop", "#end" + beats(2))`; in an
  operation the same time is the text `"#end+2beats"`, and it follows the marker on the tempo map). A cue that starts on a
  moved marker but ends at a fixed `19.5` breaks when the marker moves past it (the render refuses it, naming the note and
  what to write); put a marker on the cue's end (`marker("end", at=19.5)`) and write `end="#end"`: a later start only
  makes the note shorter.
- **Drums.** The kits (`kit=`): `"drums"` (the default: a recorded rock kit), `"studio"` (a recorded studio kit) and
  `"classic"` (synthesized). The recorded kits take `kick`, `snare`, `clap`, `hat`, `openHat`, `pedalHat`, `rim`, `tomLow`,
  `tom`, `tomHigh`, `crash`, `cymbal`, `ride`, `china`, `rideBell`, `splash`, `crash2`, `ride2`, `shaker`. The classic kit has
  `kick`, `snare`, `clap`, `hat`, `openHat`, `cymbal` (its one cymbal: write it for a crash or a ride), `tom`, `rim`. An SFZ
  kit on General MIDI keys (`kitSfz=`) also takes any GM key number 27 … 87. **Even kit** (track field `evenKit`, on for
  new kit tracks; script only): each drum plays at its measured level against the kick and snare, and each hit's very first
  milliseconds are held to 15 dB over its own loudness, so one hot drum no longer sets the master's limiter (peaks 1.7–2.7 dB
  lower at the same loudness; the drums still hit). Off (songs saved before 2026-10-25): the samples as recorded. A song saved with the old kit `"synth"` opens as `"drums"`.
  Common other names are read as these: `hihat` / `hh` / `closedHat` → `hat`, `openHihat` → `openHat`, `bd` →
  `kick`, `sd` → `snare`, `rimshot` / `sidestick` → `rim`, `handclap` → `clap` (any case, with or without - and _).
- **Plain Python in a script:** `range`, `len`, `min`, `max`, `abs`, `round`, `sum`, `sorted`, `reversed`,
  `enumerate`, `zip`, `list`, `dict`, `tuple`, `set`, `int`, `float`, `str`, `bool`, `isinstance`, `hasattr`, `any`,
  `all`, `map`, `filter`, `divmod`, `pow`, and the modules `math` and `random` (`import` them or just use them; no
  other imports). `random` starts from the same seed every run, so running the script again writes the same notes;
  `random.seed(n)` gives another draw, and `r = random(7)` makes a second generator with its own seed
  (`r.uniform(a, b)`, `r.randint(a, b)`, `r.choice(seq)`). A `class` is refused ("classes aren't allowed in
  scripts; use functions and dicts"). `print(...)` lines come back in the reply's warnings, "print: …".
- **Before the render:** every reply warns, naming them, about a held note that ends at or before its start
  (`dur={"to": …}` that a moved marker pushed past; render_mix refuses it) and about notes, hits or clips that start at or
  after the song's `length` (never heard). Warnings, not refusals: a marker moved in another app never locks the song.
- Pitches: `"C4"` = MIDI 60, `"F#3"`, `"Bb2"`, or a MIDI number.
- Names (tones, reverb spaces, EQ shapes, the plain instrument names, drum kits and drums, effect types and fields): `inspect_engine`.
- Instruments installed on this machine: `inspect_library` (`find: "cello"`); the sample packs behind the plain names, installed or missing: `inspect_library (kind: packs)`, installed with `run_model_install`. What one can play: `inspect_engine` (`what: "instrument"`)
  (a note outside a sampled instrument's range fails the render and names the range).
- Ids: tracks are named by you; notes get ids from their track and start time (`strings.n1500`), so editing one note
  never renumbers the others.
- To change one value after the script, prefer `edit_document` (`track.set`, `note.set` …): the history shows it as
  your edit, and the next script run keeps it.
