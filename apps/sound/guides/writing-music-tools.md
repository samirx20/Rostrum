# Writing tools for Sound scripts

These helpers are already available in every `run_script` script, with no import needed. Each one returns a **line**:
a plain list of notes or hits, timed in beats from the line's own start. `write(track, line, at)` puts a line on a
track. The document then holds ordinary notes that a person can edit, and running the script again keeps their edits.
The craft (when and why to use each technique) is in `inspect_guide 'writing-music'`.

**Helpers or operations.** Helpers write a part from scratch in a script. For notes that already exist (a person's, or a finished
script's) use the operations through `edit_document` instead: `note.chord`, `note.invert`, `note.strum`, `note.arpeggiate`,
`note.transpose`, `note.fit_key` (`inspect_guide 'writing-parts'`, whole calls in `'start-here'`). The arpeggio rule is the same in `arp` and
`note.arpeggiate`; `voice` has finer voicings than `note.chord`.

```python
key("D minor"); prog = ["i", "VI", "III", "VII"]           # helpers read the song's key and bar length
keys = track("keys", builtIn="grandPiano")
write(keys, comp(prog, rhythm="half", rootless=True), at=bar(5))
print(voice(prog))                                         # read what a helper writes before you place it
```

A line is a list of dicts, so you can read it, filter it and join lines with ordinary Python:

    {"pitch": "D4", "at": 0.0, "dur": 1.5, "vel": 0.7}     a note ("pitch" a list: a chord; "vel" None: the default)
    {"drum": "kick", "at": 1.5, "vel": 0.9}                 a hit

## Chords

- `roman("V7/V", key="C major")` → `"D7"`. Numerals use the degrees of the key's own scale (in A minor, `"VII"` is G
  and `"vii°"` is G dim; write `"#vii°"` for the raised one). Upper case is major, lower case minor. `°` dim, `ø`
  half-dim, `+` aug, plus a suffix as in a symbol (`"V7"`, `"IVmaj7"`, `"Vsus4"`). `b` / `#` alter the degree
  (`"bVII"` in C major is Bb), and `"/"` makes a secondary chord. Without `key=`, the song's last `key(...)` is used.
  A numeral with no key at all is an error.
- `chord_tones("Am7")` → `["A", "C", "E", "G"]`.
- Chord symbols: `C Am F#m7 Bbmaj7 G7 Dm9 Esus4 C/E Bm7b5 Cdim7 Caug C6 C69 Cadd9 C7b9 C7#9 C7#11 Cmaj7#11 C7b13
  C9sus4 C11 C13 Cmaj13 Cm13` (also `M7`, `-7`, `°`, `ø`, `+`).
- `voice(chords, voicing="led", inversion=0, voices=None, range=("G3", "D5"), rootless=False, top=None, bass=False)`
  returns the note names of each chord, low to high:

| voicing | Notes |
|---|---|
| `"led"` (default) | each chord moves as little as possible from the one before (shared notes held, the others by step), inside `range`; `top` stays on top when the chord has it |
| `"close"` | stacked as tightly as possible from the bottom of `range`; `inversion` 0 / 1 / 2 / 3 picks the lowest chord note |
| `"drop2"` / `"drop3"` / `"drop24"` | close, then the 2nd (3rd; 2nd and 4th) voice from the top dropped an octave |
| `"spread"` | close, then every other voice raised an octave (root, fifth, tenth) |
| `"shell"` | root, third and seventh (or sixth) |

  `voices` (2 … 6): with too many tones the fifth is dropped first, then the root; with too few, the root and then the
  fifth are doubled. `rootless=True` leaves the root to the bass. `bass=True` adds the bass note (the slash note) an
  octave or more below.

## Comping: `comp(chords, rhythm="hold", per=<a bar>, push=0, vel=0.7, **voicing)`

Each chord lasts `per` beats (one bar by default), voiced as in `voice` (the same arguments). `rhythm`:
`"hold"`, `"whole"`, `"half"`, `"quarter"`, `"8ths"`, `"16ths"`, `"offbeat"`, a pattern of 16ths per bar
(`"x..x..x.x-x-...."`: `x` strike, `X` accented strike, `-` hold, `.` rest), or the beats in the bar where it strikes
(`[0, 1.5, 2.5]`). `push=0.5` brings every change an eighth early.

## Bass: `bass_line(chords, style="root", pattern=None, per=<a bar>, approach=False, push=0, octave=1, gate=0.9)`

A pattern of 16ths whose characters are chord degrees, so one pattern fits every chord: `R` root (the slash note on
`"C/E"`), `r` ghost root, `8` octave, `5` fifth, `3` third, `7` seventh, `b` fifth below, `A` approach (a half step
into the next root), `-` hold, `.` rest. Styles: `root`, `half`, `pulse`, `octave`, `rootFifth`, `walking`,
`syncopated`; anything else is a `pattern`. `approach=True` turns the last note before each change into an approach
note. `octave=1` puts the roots between E1 and D#2 (`2`: E2–D#3). Match it to the track's sound: the recorded electric bass (`builtIn="bass"`) starts at A1, so use `octave=2` there; `uprightBass`, `basses`, `tuba` and `subBass` take `octave=1` (`inspect_instrument` gives any sound's lowest note). A note the sound can't play is named in `run_script`'s reply and in `inspect_diagnose` (out-of-range), before any render. `gate` sets the note length against its step.

## Arpeggios: `arp(chords_or_notes, mode="up", rate=0.5, pattern=None, octaves=1, gate=0.9, per=<a bar>, bars=None)`

Chords (each voiced in `range=("A3", "E5")` unless you give one, restarting at each change) or notes (repeating for
`bars`). Modes: `up`, `down`, `upDown`, `downUp`, `converge`, `diverge`, `order`, `random` (seeded, so the same every
run), `chord` (all notes on each step). `rate` is the step in beats (`0.25` = 16ths, `1/3` = 8th triplets). A 16ths
`pattern` (`"x.xX-x.x"`) replaces the even rate.

Use `arp(...)` when you write a new part in a script. For chords already written in the song (by a person or an
earlier script), use the operation `note.arpeggiate {rate, mode, octaves, gate, seed}` on their notes instead: it
turns each chord into its notes one after another over the chord's own length, by the same rule as `arp` (the same
modes, without `chord`), and writes plain notes (`inspect_guide 'writing-parts'`).

## Drums: `drum_grid({drum: steps}, bars=1, fill=None, every=4, fill_beats=1, crash=False, last=True, toms=("tom",))`

One string per drum, one character per 16th (16 = a bar of 4/4), each repeating over its own length: `X` accent, `x`
hit, `o` ghost, `r` 32nd roll, `t` triplet roll, `.` rest (spaces and `|` are ignored), or a list of step numbers.
Fills replace the last `fill_beats` of every `every` bars: `"snare"`, `"toms"` (down the drums in `toms`, high to
low, e.g. `("tomHigh", "tom", "tomLow")` on a kit that has them), `"roll"`, `"build"` (quarters → 8ths → 16ths →
roll), `"stop"` (everything rests). `crash=True` adds a cymbal after each fill; `last=False` leaves the final bars
plain.

## Developing a line

- `line([("A4", 0, 1.5), ("C5", 1.5, 0.5, 0.8), (["D3", "A3"], 2, 2)])` builds a line from tuples (pitch, at, dur
  [, vel]), in beats.
- `vary(line, "steps:1+displace:0.5")` applies ops (joined with `+`, applied left to right).
- `develop(line, repeat=4, vary=["same", "steps:1", "same", "end:-1"], every=None)` writes the line `repeat` times,
  each repeat `every` beats after the last (by default the line rounded up to whole bars), with repeat k getting
  `vary[k % len(vary)]`.
- `shift(line, 8)` moves a line 8 beats later; join lines with `+`.

| Op | Does |
|---|---|
| `transpose:n`, `octave:n` | moves by semitones or octaves |
| `steps:n` | moves by n notes of the key (a sequence: the same shape on another degree) |
| `invert[:note]` | mirrors the shape around the first note (or the given one), in the key |
| `retrograde`, `reversePitches` | plays it backwards in time, or keeps the rhythm and reverses the pitches |
| `displace:beats` | shifts it inside its span, wrapping round (a motif starting on the off-beat) |
| `augment[:f]`, `diminish[:f]` | stretches or shortens the timing (default ×2) |
| `thin[:grid]`, `thicken` | keeps only the notes on the grid (each held to the next), or adds passing notes into leaps |
| `double[:n]` | adds a copy n semitones away (default an octave), a little softer |
| `fit:LOW:HIGH` | folds the notes into a register by octaves |
| `end:n` | moves the last note n steps (default −1: an answer that comes to rest) |
| `quantize[:grid]`, `gate:f`, `legato`, `staccato`, `ratchet:n`, `cut:beats`, `rest` | timing and length |
| `accent:X..xo.x.`, `dynamics:0.6>1.0`, `velocity:v` | velocity: accent pattern per 16th, a swell across the line, or one level |

Timing feel (swing, small timing differences, varied velocity) comes from the performance layer, which is on by
default. You don't need to write it in. To set a swing on a track: `track.feel {swing: 0.55, swingGrid: 0.25}`
(0.25 = 16ths, 0.5 = 8ths). `track.feel` changes only what it names, so a person's other feel settings stay;
`{person: false}` turns the instrument's looseness off and keeps the swing; `{timing: null}` puts one value back to the
instrument's default.
