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
  another seed gives another draw. The `dynamics` / `vibrato` lanes are the same `automation.set` operation as
  volume / pan (lane `dynamics` / `vibrato`).

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
