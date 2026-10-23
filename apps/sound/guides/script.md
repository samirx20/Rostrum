# The Sound script API (run_script)

A script describes the whole song; `run_script` merges it into the document. Run the same script again after a
change and only what the script changed moves: anything a person changed by hand is kept and listed as held back.

```python
tempo(96); length(bar(9)); beats_per_bar(4)              # bar(1) is the start of the song
marker("drop", at=bar(5))                                 # name a moment; other times can say "#drop" or "#drop+0.5"
s = track("strings", sfz=r"C:\...\Violins.sfz", volume=0.8)   # instrument from sfz= / builtIn= / kit= / kitSfz=
s.note("D4", at=beat(0), dur=beats(4), vel=0.7)
s.chord(["D3", "A3", "F4"], at="#drop", dur=beats(2))
d = track("drums", kit="synth"); d.hit("kick", at=beat(0)); d.hit("snare", at="#drop+0.5")
v = track("door"); v.clip(r"C:\...\door.wav", at=3.0, in_=0.42, length=1.2)
s.effect("reverb", space="hall", mix=0.3)
s.automate("volume", [(0, 0.2), ("#drop", 0.9)])
master(loudness=-16); master.effect("limiter", ceiling=-1)
```

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
vln.bend([(bar(5), -0.25), (bar(5) + 0.5, 0)], range=2)    # pitch wheel -1 … 1 (× range semitones, 2 unless set)
keys = track("keys", builtIn="feltPiano")
keys.sustain([(0, 0), (bar(2), 0), (bar(2), 1), (bar(3), 1), (bar(3), 0)])   # pedal CC 64: down bars 2–3 (steps)
vln.phrase(bar(5), bar(9), vel=[(0, 0.5), (1, 0.9)])  # velocity along the phrase, for notes that wrote no vel
f = vel_curve([(0, 0.5), (1, 0.9)], bar(5), bar(9)); vln.note("D4", at=bar(6), dur=1, vel=f(bar(6)) + 0.15)
vln.humanize(seed=3, timing=0.012, velocity=0.06)   # every note / hit on the track, ±12 ms, ±0.06
```

- `legato`: overlapping notes glide as one line (write each note slightly longer than its gap). `swell`: long
  notes swell in. Both are per track, sampled tracks only.
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
  (`param:<id>`). `inspect_plugins` lists what is installed with each setting's id, range and default. `state` is
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
  to the first change, then each change's bpm (no ramps: a ramp is several changes). The screen's ruler, the ids,
  the checks and the engine's render all read the same map. A tempo change can't sit on a marker.
- **What follows a tempo change:** things written in beats stay on their beat (they move in seconds); things in
  seconds stay at their moment (their beat moves). Markers follow the same rule: a marker at `bar(5)` stays on bar 5,
  a marker at `12.0` stays at 12 s. Write in beats what belongs to the music, in seconds what belongs to the picture.
- **Moving a section:** `edit_document` `{"op": "section.move", "target": ["section.drop"], "args": {"by": {"beats": 8}}}`
  (or `"by": -2.5` seconds) moves the section and everything that starts inside it (notes, hits, clips, designed
  sounds, voice lines, markers, tempo and key changes, other sections, automation points) in one undo step. Each
  time keeps its form; a time on a marker that moves with it follows it. Effect envelopes inside effects don't move.
  In the arrangement: drag the section's bar (Ctrl = off the grid).
- **Keys** are for you and the screen (the readout shows the key at the playhead): `doc/keys.py` has `scale`,
  `in_key`, `snap` (nearest note of the key). They change nothing in the sound.
- **MIDI:** `edit_import_midi` `{path, song_map}` imports a .mid as one undo step (channel 10 becomes drum hits on
  the synth kit; other channels a built-in instrument from the GM program family, to change after); `render_midi`
  writes the document's notes, hits, sustain / expression / mod wheel / bend lanes (CC 64, CC 11, CC 1, the pitch
  wheel, bend range as RPN 0; import reads them back), tempo map, time signature, keys, markers and sections (as
  cue points) to `renders/<item>/midi/<item>.mid` (the screen: Export › What for › MIDI file). What MIDI can't carry comes back as a warning. Clips, designed sounds and
  voice lines are audio and are not written.
- **A MIDI keyboard** (screen): arm a track, "Record keys" (shown only with a keyboard connected) records while the
  mix plays; Stop puts the take on the armed track in beats, one undo step. The sound you hear while playing is a
  monitor (an SFZ track plays its file, others a plain synth); the render plays the track's instrument.

## Notes

- Times: seconds (`2.5`), `beat(n)` (from the start, 0-based), `bar(n)` (1-based), or a marker (`"#drop"`).
  Lengths: seconds or `beats(n)`.
- Pitches: `"C4"` = MIDI 60, `"F#3"`, `"Bb2"`, or a MIDI number.
- Names (tones, reverb spaces, EQ shapes, built-in instruments, drums, effect types and fields): `inspect_engine`.
- Instruments installed on this machine: `inspect_library` (`find: "cello"`). What one can play: `inspect_instrument`
  (a note outside a sampled instrument's range fails the render and names the range).
- Ids: tracks are named by you; notes get ids from their track and start time (`strings.n1500`), so editing one note
  never renumbers the others.
- To change one value after the script, prefer `edit_document` (`track.set`, `note.set` …): the history shows it as
  your edit, and the next script run keeps it.
