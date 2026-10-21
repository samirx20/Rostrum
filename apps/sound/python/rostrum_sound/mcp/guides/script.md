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
