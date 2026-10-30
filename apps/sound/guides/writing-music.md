# Writing music: read this before you compose

Better writing makes the biggest difference to how a piece sounds, more than better sounds or a better mix. This page
covers the craft: how parts are built and how they move. The tools that write the notes for you are in
`inspect_guide 'writing-music-tools'`, and the script basics (tracks, `bar()`, `beats()`, markers) are in
`inspect_guide 'script'`. Short fragments here show one technique each. They are not pieces to copy: every piece starts
from its own brief.

## Plan first

The plan becomes the first lines of the script, and the whole piece one script under one name (`inspect_guide 'start-here'`, "The loop").

1. **Form first.** Write the sections with `section(name, at, end)` and give each one a job: set up, state the idea,
   build, peak, release. Decide where the high point is (usually around two thirds of the way in) and what makes it
   the high point: register, density, harmony, or a new instrument coming in.
2. **Harmony as one list.** Write the progression once (`prog = ["i", "VI", "III", "VII"]`) and drive the chords,
   bass and arpeggios from that same list, so the parts agree.
3. **Give every part its own register and its own job** (see *Arranging by register*). Two parts doing the same job
   in the same octave cancel each other out.
4. **Write the lines, then develop them.** Write a short idea and grow it (sequence, invert, extend, thin out) rather
   than writing new material for every bar.
5. **Check with the look tools** (end of this page), then adjust the notes, not just the levels.

## Harmony and voicing

- **Voice leading:** when the chord changes, keep shared notes where they are and move the other voices to the nearest
  note of the new chord. This one habit is what separates "chords" from "a progression". `voice(prog)` does this by
  default (`voicing="led"`). Use `top="E5"` to keep a note on top whenever the chord has it.
- **Inversions** keep the bass line smooth. `C – G/B – Am – F` walks down by step where `C – G – Am – F` jumps.
  Write the slash chord (`"G/B"`), or use `inversion=1` on a written voicing.
- **Close or open.** Close voicings (`"close"`) sound compact and bright, and sit well in the middle range. Open
  voicings (`"spread"`, `"drop2"`) sound wide and warm and leave room for a melody. Keep chords open below about C3:
  close intervals down there turn to mud (the harmony check flags this).
- **Leave the root to the bass.** With a bass part playing, `rootless=True` gives the keys or pad the colour notes
  (3rd, 7th, 9th) and stops the low end doubling up.
- **Colour with intent.** Sevenths and ninths soften a progression. A borrowed chord (`"bVI"`, `"bVII"` or `"iv"` in a
  major key) darkens a moment. A secondary dominant (`"V7/V"`) pulls hard into the next chord. One colour chord at the
  right place does more than colour everywhere.
- **Harmonic rhythm** (how often the chord changes) drives the energy. Two bars per chord feels spacious, one chord per
  bar moves forward, and two per bar presses on. Speeding up the changes before a cadence is a classic build.
- **Anticipation:** `push=0.5` brings each change in an eighth early. It works for pop, funk and driving cues, but not
  for a chorale.

## Bass motion

- The bass carries the harmony: **roots on strong beats**, other chord notes (5th, 3rd, octave) in between, and
  **approach notes** (a scale step into the next root; `chromatic=True` for a half step, which can leave the key and is then named in the reply) just before a change. `bass_line(prog,
  style="walking", approach=True)` writes this; a pattern like `"R--r..8-R-.r5-8r"` shapes your own.
- **Lock with the kick.** A bass note on every kick, and few bass notes where the kick isn't, makes a groove feel
  like one instrument. Write the kick pattern first, then the bass rhythm to fit it.
- **Pedal point:** hold the bass on one note while the chords change above it. This builds tension; releasing it
  resolves.
- **Keep the low notes alone.** Under about E2 only one part should play at a time (the bass), because the low end of a
  mix has room for one thing.

## Melody and motif

- **A motif is 2 to 5 notes with a clear rhythm.** Repeat it so the listener learns it, then change it so they stay
  interested. A common shape is: state it, repeat it, vary it, then answer it (`develop(motif, repeat=4,
  vary=["same", "same", "steps:1", "end:-1"])`).
- **Strong beats on chord notes,** passing notes between them. A leap is followed by a step back the other way.
- **Contour:** give each phrase one high point, and put the piece's highest note at its climax only.
- **Breathe:** leave rests. A phrase is usually 2 or 4 bars, and the gap at its end is part of it.
- **Counter-line:** a second line moves when the melody holds and holds when the melody moves, in another register,
  mostly in contrary motion.

## Groove and feel

- **Drums are a pattern plus variation.** Keep the main pattern steady for 2 to 4 bars, then mark the end of a phrase
  with a change: a fill, a dropped beat, or an open hat. `drum_grid(..., fill="snare", every=4)` writes fills into
  the pattern.
- **Dynamics inside the beat:** accents on the main beats and **ghost notes** (`o`, very soft) between them. A hat
  that is the same level on every step sounds mechanical; one that is loud on the beat and soft between sounds played.
- **Swing and timing** come from the performance layer (below). Keep written notes on the grid unless you want a
  specific push or drag that is part of the part itself.
- **Space is groove.** A rest on the "and" before a downbeat makes the downbeat land harder.
- **A downbeat on a marker:** `downbeat(bar(3), at="#logo lands")` puts bar 3 on the marker (the bars before it become
  the run-up), so the groove's own downbeat lands there: put the accent on it (`d.hit("kick", at=bar(3))`, a crash).

## Arranging by register

Give every part its own range and its own job, and the mix sorts itself out:

| Register | Roughly | Job |
|---|---|---|
| Sub and bass | E1–E2 | the root and the pulse: one part only |
| Low middle | E2–C4 | warmth: open chords, cello lines; keep it thin, as it muddies first |
| Middle | C4–C5 | the chords and comping, the human-voice range |
| Top | C5–C7 | melody, sparkle, arpeggios, high strings |

- **Density follows the form:** start with a few parts and add one at a time. Something new should enter at every
  section; taking things out before a peak makes the peak bigger.
- **Doubling** a line an octave up (`vary(line, "double")`) makes it bigger without making it busier.
- **When a section adds parts, lift what was there.** A piano, pad and guitar that all stay in the low middle when
  drums, bass and strings arrive pile up at 250 Hz–1 kHz: the mix gets louder but darker. Move one of them up an
  octave, or thin its chord, as the new parts come in; `look_sound` (`what: "spectrum"`) shows the bands before and after.
- **Rhythm layers:** long notes (a pad), a middle pulse (comping, an arpeggio) and fast detail (hats, 16th notes).
  Too many parts at the same speed blur together.

## Dynamics and phrasing

- **Shape every phrase:** it swells towards its high point and falls away after it. In a script, use
  `t.phrase(start, end, vel=[(0, 0.55), (0.6, 0.85), (1, 0.6)])` on a part, or `vary(line, "dynamics:0.6>1.0")`.
- **Shape the whole piece too:** `t.shape` (below) is the one-line way; the expression lane
  `t.dynamics([(time, level), …])` gives a swell over several bars as a level under the notes,
  the way strings and brass actually play. A note's own `dynamics=[(0, 0.4), (1, 1.0)]` runs across that one note
  (x is the fraction of its length), not song time.
- **A build to one big moment** under a loudness target (a crescendo, a hit, a tutti): how wide to make it, how long
  the loud moment must last so the limiter doesn't flatten it, and how to stage the hit: `inspect_guide
  'scoring-to-picture'` › "Builds, hits and climaxes under a loudness target".
- **How far a build travels** is the script's, not the master's: a loudness target turns the whole file up or down,
  so the distance between the opening and the peak stays as written. Velocity moves recorded instruments a long way
  (measured on a held chord, against velocity 1.0): built-in `strings` 0.6 → −8.5 dB, 0.5 → −10, 0.3 → −16,
  0.2 → −22; `horn` 0.5 → −11, 0.3 → −21. A swell that reads as one over 30 s or more (strings alone at 0.2–0.3 under
  a `t.dynamics` lane rising to 1.0, parts added on the way up, the peak a tutti) travels about 25–35 LU from its
  first bars to its peak; one written at 0.5–0.6 from the start travels about 15.
  Coming down is the same in reverse: parts drop out, the lane falls, a soft last chord dies away inside the file
  (`ending("ring", at="#end")` lands the parts on the home chord and leaves the tail room; `ending("fade")` writes a fade).
  `look_sound` shows the short-term curve; when the brief asks for a quiet start or ending the render measures it
  (`loud_opening`, `loud_ending`: 20 LU or more under the loudest 3 s passes).
- **Sustained instruments** (strings, brass, pads) need long notes and slow swells. Short notes on a pad sound like a
  keyboard demo. **Plucked and struck instruments** (piano, guitar, marimba) need movement: broken chords, arpeggios,
  pedal.
- **Piano:** use the sustain pedal (`t.sustain(...)`), and lift and press it again at each chord change so the
  harmonies don't blur.

## Keep it moving: shape

`t.shape(what, from_, to, over=(start, end), curve="linear")` makes one part's volume, brightness or articulation
follow a curve over bars, in one line:

```python
strings.shape("vol", 0.5, 1.2, over=(bar(1), bar(13)), curve="late")     # swell, most of it near the end
horns.shape("bright", 0.2, 1, over=(bar(9), "#climax"))                   # a lowpass opening up into the climax
violins.shape("art", "sus", "trem", over=(bar(5), bar(9)))                # sustained -> tremolo halfway through
```

- `"vol"` multiplies each note's and hit's velocity by the curve where it starts (1 = as written, up to 2, velocity
  kept 0 … 1). Velocity picks the sample layer, so instruments with soft and loud recordings change sound along the
  curve, as players do. A note longer than a beat with no `dynamics` of its own swells inside itself with the curve.
- `"bright"`: 0 … 1 (0 ≈ 250 Hz, 1 = 20 kHz) or Hz; written as one lowpass EQ on the track (`<track>.eq_bright`).
- `"art"`: names from the track's `articulations`, `""` for its main sound; notes switch where the curve passes its
  middle. Notes written with another articulation keep theirs.
- `curve`: `"linear"`, `"late"` (most of the change near the end), `"early"` (most near the start), `"smooth"`
  (S-shaped). `over` takes every time the script takes (`bar(9)`, seconds, `"#climax"`, `"#climax-0.5"`).
- A shape changes the whole part, not only `over`: before a part's first shape of a kind the value holds at its
  `from_`, after the last at its `to`, between two shapes at the earlier one's `to`; several shapes of one kind on a
  part join into one curve (they do not multiply). `brass.shape("vol", 0.3, 1, over=(bar(18), bar(19)))` plays a stab
  at bar 10 written vel 0.9 at 0.27. To leave the notes before it as written, start the curve from 1 there:
  `brass.shape("vol", 1, 1, over=(0, bar(18)))` first. It applies after `phrase` and before `humanize`; a re-run gives
  the same values.

## The performance layer (on by default)

Every instrument plays your notes the way a player would. It adds small timing differences, varies the velocity from
note to note, accents the strong beats, plays sustained instruments legato with vibrato on held notes, and strums
plucked chords. This is set up for each family of instruments, and it is the same on every render. You don't need to
humanize by hand.

- Turn it off on a track with `track("seq", builtIn="pluck", perform=False)` when the part should be exactly as written
  (a sequencer line, a click, a tight electronic part).
- Change it with an object: `perform={"swing": 0.3, "timing": 4}` (every field: `inspect_guide 'writing-parts'`).
- Your written velocities and phrase shapes still count: the layer varies around them.

## Checking without ears

You can't hear the result, so check what you can measure and say plainly what you can't.

1. **Before rendering:** `look_arrangement` shows every part by pitch over the numbered bars and sections, shaded by its written level (velocity × volume), with each part's level in dB and its lowest and highest note. The parts' entries against the bars,
   how registers stack and how the written levels run are all in the picture; `render_audition` then plays any stretch you want to hear (about a second).
2. **Harmony:** `look_music` with `what: "harmony"` reports the chord in each bar and checks the written notes: notes
   out of the instrument's range, voices crossing, close intervals too low, and notes outside the key. Each one is a fact about the written notes; change what you didn't mean. It reads the written notes, so no render is needed.
3. **After rendering:** `look_sound` with `what: "loudness"` draws the short-term curve; its
   summary names the loudest moment and its time (the loudest 3 s and 0.4 s, and the highest sample).
   `what: "levels"` shows whether a part is buried. `what: "low_end"` and `what: "clash"` show low parts or two parts
   in one range fighting each other.
4. Print what a helper wrote (`print(voice(prog))`) to read the notes before you commit to them.

Whether it is musical, and whether it moves anyone, is decided by a person listening. Say that in your report.
