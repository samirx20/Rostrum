# The Sound script API (run_script)

**The whole piece is one script, under one name.** Write it, run it with `run_script` and `look: true` (it renders and listens), read the listening
check in the reply (loudness, the weakest asked moments with their fixes, faults such as "leading silence", "tempo far from
the brief's" and "stop lands soft"), edit the script and run it again under the same name. `edit_document` is for one-off
touch-ups. To make an asked moment read (a hit out of silence, a band that really stops, a drop that is a gap), see "Moments that read" below.

Replies open `NOT DONE:` with each fault (id, when, fix) or `DONE:`. A delivery (`render_mix`, or `run_script` `look` with `folder`) is refused while a fault is open (the file is kept as `<name>.NOT-DONE.wav`) unless `keep: {id: "why"}` explains it, and every why quotes the brief (in quotes, or 3 or more of its words in a row) where it asks for that fault: `brief("...")` in the script stores the brief's own words on the song (a dull top is kept for "dark, muffled", never for "a piano chord progression"); with no brief stored, or a why that does not quote it, the keep is refused and the fault's fix says why; a fault on the moment the brief asked for (its words say so) can be kept only after a render that tried the fix, and only when it measures within the stated distance of passing (its words say what passes and from where it may be kept); further off, fix it, or move the moment itself in the script (`moment(name, at=...)` or `expect`) when the brief allows another time.

- **Same name = replace.** A track, note, hit, effect, automation lane, marker, section or tempo change you delete from the
  script is gone after the next run; a new tempo moves every beat-written time and keeps a person's edits; a changed value
  changes in place. **A new name that makes the same tracks is refused** (`song_v2` re-making `song`'s tracks would double every note; the
  error names the script to run under, and nothing changes); a new name with new track ids adds parts beside it.
- **Held back.** Anything a person (or an `edit_document` call) changed by hand is kept and listed as held back, saying who
  got there first ("already changed by agent:mcp"); pass `force` with the ids to take over. So keep each setting in one place:
  the script, until the last touch-up. A track's `volume`, `pan`, `output`, a master target and every effect setting
  are script arguments too (`track(..., volume=0.8)`, `master(loudness=-16, maxLimit=4)`).
- **A run that fails changes nothing** (no half-made track is left): the error names the script and the line; an unknown track
  method lists what a track can do, an unknown name lists the script's names. A run that merged says so, even when a note ends
  before it starts (a warning naming the note, see "Before the render"). Times can name the song's markers (`"#drop"`,
  made with `marker.add`) and the project's without the script restating them.

**A script's shape** (a technique; every name is below):

```python
brief("<the brief you were given, word for word>")      # 0. a kept fault quotes it (keep)
tempo(96); key("F major"); length(bar(17))                 # 1. the song's map: tempo (changes), meter, key, length
marker("lift", at=bar(9)); section("verse", bar(1), bar(9))  #    sync points as markers, sections as named spans
CHANGES = {1: "F", 3: "Bb", 5: "Dm7", 7: "C"}              # 2. the music as data: bar -> chord, a dict you edit
def comping(first, last, vel): ...                         #    a section is a function: call it where it plays
for b in range(1, 17, 2): ...                              #    loops over bars write what repeats
keys.humanize(seed=2); keys.dynamics([(0, 0.5), ("#lift", 1.0)])   # 3. one pass for how it is played
keys.effect("reverb", space="hall", mix=0.3)               # 4. the mix block last: effects, levels, buses
master(loudness=-16, truePeak=-1)                          #    and the master target
```

**Bars first.** Write notes and hits on the beat grid (`at=bar(5) + beats(1)`, `dur=beats(2)`): a tempo change then moves
them with the music. A bare number is seconds and never moves; keep it for sync points, ideally as a marker. When nearly
every note of a run is in seconds (8 or more, 90 %), the reply says so.

**Landing on a time.** `downbeat(bar(n), at=T)` puts bar n at T seconds (music before bar 1 is a pickup, so a sync point
lands on a bar line without a silent start); `land(bar(n), at=T, ramp_from=bar(m))` glides the tempo so bar n lands at T.
`T` is seconds or a marker (`at="#logo lands"`, `"#logo lands+0.5"`, `"#logo lands" + beats(1)`). Both are under
"Landing on a time" below, with the tempo formula and the marker form (`marker("hit", at=31.5)`, `at="#hit"`).
Render with `expect` (`{"kind": "tempo", "bpm": N}`) to be told when the tempo drifts from the brief's.

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

Check what you wrote when the render's check names something: `look_arrangement` draws every track's notes and hits with the bars, sections
and markers, and says which tracks start on each marker.

## Mix routing: buses, sends, ducks, dialogue

```python
verb = bus("verb", volume=0.8); verb.effect("reverb", space="hall", mix=1.0)   # a bus: a channel tracks feed, with its own effects
keys = track("keys", builtIn="piano", output="verb")                           # plays into the bus instead of the master
pad.send("verb", level=0.3)                                                     # part of a track goes to a bus as well
vo = track("vo", role="dialogue"); vo.clip("media/vo.wav", at=0)               # speech: a voice-over file, an interview
music.duck(depth=0.7)                                                           # no `under`: dips under every dialogue track
bass.duck(under=["kick"], depth=0.5, attack=0.005, release=0.15)                # under a kick: a short pump per hit
```

- `role="dialogue"` marks a track as speech; a voice track (it speaks lines) is dialogue already. Left out, a track is music.
- A duck under dialogue only (every track it is under is dialogue, or no `under` at all) dips for **whole lines**: it keeps
  the bass, holds 0.3 s across the gaps between words and comes back in pauses. Under anything else it pumps per hit.
  `voice=False` keeps a pump even under speech; `voice=True` forces whole lines. Worked out at every render, so a dialogue
  track added later counts. `duck()` with no `under` in a song with no dialogue track fails the render, naming the fix.
- `duck(...)` takes `under`, `depth` (0 to 1), `attack`, `release`, `hold` (seconds), `voice`, `lookahead`. To duck a bus,
  duck each track that feeds it. Check it: the reply's fault `duck:<track>` names a dip under 3 dB while the voice speaks.

## Effects and the master: every setting, with its unit

`s.effect(type, **settings)` adds an effect to a track (`inspect_operations` `effect.add` / `effect.set` take the same
names). Every number is a plain number in the unit below, never `{"db": ...}` and never milliseconds. The full list, with
defaults and ranges, is what `inspect_engine` returns with `detail: "full"` (`data.effects`, `data.master`); `inspect_engine` with `name: "compressor"` (or `"master"`) gives one effect's settings alone: it is read from the same table the
checks use, so it cannot disagree with them. A setting marked "curve" also takes a list of `[time, value]` points.

| Effect | Settings (unit) |
|---|---|
| `compressor` | `threshold` dB (-80 to 0), `ratio` :1 (1 to 30), `attack` seconds (0.0001 to 1), `release` seconds (0.001 to 5), `makeup` dB, `knee` dB |
| `eq` | `bands`: a list of `{shape, freq (Hz), gain (dB), q}`; shapes `lowshelf`, `highshelf`, `peak`, `lowpass`, `highpass`, `notch` |
| `reverb` | `space` (below), `mix` 0 to 1, and with a `freeverb.*` space `decay` seconds, `damping`, `size` |
| `delay` | `time` seconds, `feedback` 0 to 0.98, `mix`, `pingPong` true/false, `damp` |
| `saturate` | `drive` 0 to 1, `mix` |
| `tape` | `wow`, `flutter`, `age`, each 0 to 1 (`wow` a slow pitch drift of up to about 15 cents, `flutter` a fast waver, `age` adds saturation and a darker, thinner tone); `hiss`, `crackle`, each 0 to 1, default 0 (a record's surface: a soft noise bed and the ticks and pops of a played record) |
| `limiter` | `ceiling` dB, `release` seconds |
| `width` | `width` 0 to 2 (1 = unchanged), `monoBelow` Hz. Widens only what is already stereo: on a mono recording (Wurlitzer, Rhodes, the basses, the kits' close mics) it does nothing; use `chorus` or `tremolo` with `stereo` on that track, pan it, or send it to a stereo reverb or delay |
| `chorus` | `rate` Hz (0.05 to 10, default 0.8), `depth` 0 to 1 (how far the copy sways, up to 5 ms; 0.5), `mix` 0 to 1 (0.5 the classic chorus, 1 only the swaying copy: a vibrato), `spread` 0 to 1 (1: left and right sway in opposite directions, so even a mono source comes out wide; 0: no widening) |
| `tremolo` | `rate` Hz (0.1 to 20, default 4), `depth` 0 to 1 (how far the level dips; 0.5), `stereo` 0 to 1 (0: both sides dip together; 1: one side dips while the other rises, an auto-pan like a Rhodes Suitcase's stereo vibrato, which widens a mono source) |
| `gate` | `threshold` dB, `ratio`, `range` dB, `attack` / `hold` / `release` seconds |
| `deess`, `dehum` | see `inspect_engine` |

Reverb spaces: `dry`, `room`, `hall`, `cathedral`, `shimmer`, and the adjustable `freeverb.room`, `freeverb.hall`,
`freeverb.cathedral`. Tones (`tone=` on a track): `neutral`, `muffled`, `warm`, `sub-boost`, `bright`, `voice-clarity`, `radio`.

```python
s.effect("compressor", threshold=-24, ratio=4, attack=0.01, release=0.2)   # dB, :1, seconds
s.effect("tape", wow=0.3, flutter=0.2, age=0.5, hiss=0.3, crackle=0.4)
master(loudness=-14, truePeak=-1, glue=0.2, fadeOut=1.8)
```

`master(...)` takes `volume` (gain 0 to 4), `normalize`, `loudness` (LUFS, -60 to 0: giving it turns `normalize` on),
`truePeak` (dBTP, -12 to 0), `gentle` (on by default) and `maxLimit` (dB, 0 to 12, default 2: with `gentle` on, the
limiter never pulls the loudest moment down by more than this; a mix that would need more is turned down as a whole,
so playback lands under its loudness target; a render (`render_mix`, `look`) is pushed onto the target for that file and says how many dB of limiting it took, the song keeping this value), `glue` (0 to 1), `reverb` and `trackReverbSpace` (spaces), `fadeIn` and `fadeOut` (seconds, 0 to 600) and
`safetyClip`. Effects on the whole mix go on the master the same way as on a track: `master.effect("eq", bands=[{"shape":
"highshelf", "freq": 4000, "gain": 4, "q": 0.7}])` (the dull-top fault names the gain that clears it).

An instrument's playable range (a recorded one has no samples outside it, and the render refuses the note):
`inspect_engine {"name": "<builtIn name>"}` before writing its part.

There is no bit-crush effect. For a worn, lo-fi sound the tools are `tape` (wow, flutter, age, and a record's surface:
hiss and crackle), `saturate` (drive), an `eq` low-pass (`lowpass`) and high-pass, a `reverb`, a `delay`, the `rhodes`
electric piano, and the performance layer's swing and lean (below).

**Tape settings.** All three run 0 to 1 and default 0.2. `wow` is a slow pitch drift (up to about 15 cents at 1; the
"seasick" one), `flutter` a fast waver, `age` adds saturation and a darker, thinner tone. For a gentle worn sound stay
under about 0.4 on `wow` and `flutter`; the number a look tool reports (`look_music pitch`: drift and vibrato per note)
shows what it did, whether it is pleasant is for a person to hear.

**Record surface.** `hiss` and `crackle` (0 to 1, default 0) add a record's surface before the tape's saturation and
tone, so `age` darkens it too. They are fixed levels, not following the music: `hiss` 1 is a noise bed near -34 dBFS,
`crackle` 1 about 34 ticks a second on each side and a pop about once a second (the loudest near -12 dBFS). Ticks land
on each side apart, so the surface also widens a narrow mix. It sounds for as long as the track does, quiet parts
included, and the same in every render. One bed for the whole song: a `tape` with only `hiss` / `crackle` on one track
that runs the full length (or on a bus every track feeds), with `wow`, `flutter` and `age` at 0 there if the tape
colour is already on the keys.

**Lo-fi, as techniques** (settings to start from, not a finished piece; move each to taste and check with the look tools):

- *Dull the top:* an `eq` band `{"shape": "lowpass", "freq": 3500 to 6000, "q": 0.7}` on keys, vibes and the drums, so
  nothing sparkles; a `highpass` near 60 to 80 Hz on the keys so they leave the bass room.
- *Warble and wear:* `tape` on the keys and the lead, `wow` 0.2 to 0.4, `flutter` about 0.2, `age` 0.4 to 0.7; not on the
  bass or kick, where pitch drift reads as out of tune.
- *Grit:* `saturate` with `drive` 0.2 to 0.5 on the drums and the bass; a compressor with a slow `release` (0.2 to 0.4 s)
  on the drums holds the hits together.
- *Laid back:* `perform={"swing": 0.3 to 0.6, "lean": 5 to 15}` on the drums and keys (see "Swing" below); keep the notes on the grid.
- *Space:* a small `room` reverb with a low `mix` and a dark `delay` (`damp` 0.5 or more) on the lead, not on the bass.
- *Surface:* `tape` `hiss` 0.2 to 0.4 and `crackle` 0.2 to 0.5 on one full-length track or bus (see "Record surface"),
  so the bed runs under the whole piece; with a voice over it, keep `crackle` lower during the voice (a curve).
- *Width:* the Rhodes, the basses and the Wurlitzer are mono recordings, so a mix of them is near mono (`look_sound` "stereo"
  correlation near 1) and `width` cannot widen it. On the keys: `chorus` (`rate` 0.5 to 1, `depth` 0.3 to 0.6, `mix` 0.3 to 0.5,
  `spread` 1) or `tremolo` with `stereo` 1 (`rate` 3 to 6, `depth` 0.3 to 0.7); a stereo reverb adds width too. Keep the bass
  and kick centred. Render and compare the correlation before and after.
- *Keys:* `rhodes` is a recorded Rhodes; `electricPiano` is a Wurlitzer (brighter, more bark).

## Ending a song

A song stops at its `length`. What a clean end needs, with what exists today:

- **End on a marker (a clean, real ending).** The music stops itself on the marker: a short last chord or hit ON it
  (a staccato chord, a kick with a choked cymbal, notes no longer than a beat), held notes ending on it
  (`end="#end"`), and the song's `length` 1–2 s after it so the tail dies away in the room, Ring out on. When the brief
  asks for a clean ending, or a marker named end / ending marks it, two endings are faults: the delivery's fade of a
  ring past the length (`faded_end`), and a file that stops while still playing, within 12 dB of its loudest
  (`chopped_end`: held notes cut at the length). `ring_out(False)` (after `length`) stops the song at its length, its last
  0.1 s smoothed (`ring_out(False, soft_end=False)`: a dead stop): for a sound that has already died away there.
- **Let it ring.** A note ends where you wrote it, and the instrument's own release and any reverb ring on after it. With
  **Ring out** (the song field `ringOut`, on in every new song) a sound still ringing at `length` plays on until it dies away
  (under -60 dBFS, at most 6 s more) and the engine's file ends there; a note held past `length` is let go at it, and a note that
  starts at or after `length` is not heard (both are warned, in `run_script` and `render_mix`). `length(bar(21))` after a chord let
  go at bar 21 rings it out. **The file `render_mix` delivers is exactly `length` long** (a 40 s song is a 40.00 s file): the ring
  that would run past it is faded out over the last second inside it, and the reply's warnings say how much was cut off; to have
  the tail, end the music earlier or set a longer `length`. `render_mix` with `ring_past_length: true` lets the
  file run on up to 2 s past it (a number: up to that many seconds); the Export sheet lets it run until the ring has died away. Songs saved before 2026-10-25 open with Ring out off (they sound as they did): there the
  file stops at `length`, so leave the tail room yourself.
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
- **`trim`.** With a `length` set, `render_mix` never cuts below it (trim has nothing to take off: the file is the length you asked
  for). Without a `length` (or with `ring_past_length`), it trims the end only where the sound is below -80 dBFS; the reply says
  `trimmed: false` when sound above that runs to the end. Trim removes silence; it does not fade anything. Pass `trim: false` to keep
  the engine's full file.

## Landing on a time: through the tempo, or in seconds

A sync time (a lift at 20.0 s, a stop at 36.0 s) can be met three ways, and none needs the song's tempo bent (132 bpm
asked stays 132; a tempo nudged to 133.3 to make a bar line fall right is heard and marked down). Pick by what lands there.

**1. An off-grid moment: write it in seconds.** `at=36.0` is a time in seconds, `at=bar(21)` is a bar, so a hit, a stop or
a chord can sit exactly on the picture while the music around it stays on its grid. A marker names it once:
`marker("stop", at=36.0)`, then `at="#stop"` for every part that lands there (`"#stop-0.2"` is a little before it). Best for
one accent; the bars around it don't move.

**2. Move the whole grid: `downbeat(time, at)` and a pickup.** Bar `n` at a steady `bpm` starts `60 * beats_before / bpm`
seconds after bar 1, so to put bar 21 of a 4/4 song at 132 bpm on 37.0 s, bar 1 starts at `37.0 - 60 * 80 / 132 = 0.636 s`.
`downbeat(bar(21), at=37.0)` does that sum on the tempo map written so far (tempo changes and ramps included) and stores
it as the song's `gridStart` (the time bar 1 begins; 0 when not set): the tempo, the bars and the click all keep their
values. The time before bar 1 is a pickup (an anacrusis), not silence: write it in seconds with `seconds_of`, which turns
a beat before bar 1 into its file time: `t.note("G4", at=seconds_of(bar(1) - beats(1)), dur=beats(1))` is the beat
leading into bar 1 (`bar(1) - beats(1)` itself is refused: beat times on the grid start at bar 1). Over 0.25 s of pickup
the reply reminds you to fill it. When bar 1 would have to start before 0 s, the refusal names the bars that do fit
("bar 20 lands at 36 s with a 1.45 s pickup") and the `land` call below.

**3. Push into the moment: `land(time, at, ramp_from)`.** The tempo glides from `ramp_from` up (or down) to a peak halfway
and back, so `time` lands exactly at `at` and the tempo held before `ramp_from` plays on after it, unchanged. Over `n`
beats at `a` bpm the music takes `60 * n / a` seconds; a glide out to `p` and back takes `60 * n * ln(p/a) / (p - a)`, and
`land` solves `p`. It moves the time by about half the peak change: bar 21 at 132 bpm is at 36.36 s, so landing it
on 36.0 s (0.36 s early) over bars 15-21 (24 beats, 10.9 s) needs about 3.3 % on average, a peak near 7 %: the reply
says "tempo 132 -> 141.2 -> 132 bpm over bar 15 - bar 21". Past 8 % it is refused and names a ramp long enough. Best
where the music can lean in (a build, a run-up); write `tempo(...)` and the other tempo changes first, then `land`.

**By name.** `downbeat` and `land` take a marker for `at` (the song's, the script's or the project's: `at="#logo lands"`,
`"#logo lands-0.25"`, `"#logo lands" + beats(1)`), and `seconds_of("#logo lands")` gives its seconds. The marker is read
where it is when the script runs, and the reply says the seconds it used; when 2D moves the marker, run the script again
to land the grid on its new time (notes written `at="#logo lands"` follow it without a run). `length("#end")` and
`section("verse", "#a", "#b")` keep the marker itself, so they follow it.

**A marker 2D sees: `marker(name, at, shared=True)`.** A script's markers are the song's own; with `shared=True` the marker
is published to the project's markers (the ones `edit_markers` changes and `inspect_markers` shows, that 2D follows),
in seconds, when `run_script` merges the script. Run again with the same name and time: nothing changes. A project
marker of that name at another time (someone moved it) is a loud error naming both times: write the script's marker at
that time, or use `"#name"` without making it, or move it with `edit_markers`. Removing `shared=True` later leaves the
project marker where it is.

Order: `downbeat` and `land` work on the tempo map written so far, so write the tempo, the tempo changes and the time
signature first. Each landing is checked again when the script ends: a tempo change written after it that moves the
landed bar is refused, naming it. Check the result with `look_music` (`what: "events"`, `expect: [37.0]`, a tolerance
of 0.05 s): the reply says how far off each onset is. `beat()` takes fractions of a beat (`beat(36.83)`); `bar(n)` is
where bar `n` starts.

```python
tempo(132); beats_per_bar(4)
downbeat(bar(21), at=37.0)                                   # bar 1 starts at 0.636 s; the tempo stays 132
pno = track("keys", builtIn="piano")
pno.note("D4", at=seconds_of(bar(1) - beats(1)), dur=beats(1))   # the pickup into bar 1
pno.chord(["D3", "A3", "F4"], at=bar(21), dur=beats(4))          # on 37.0 s
```

## Building into a moment: `build_to`

`build_to(target, over, parts)` writes the run-up into a time as ordinary notes and hits, from `over` before the target up
to it. The tracks, pitches and drum are yours; each part is a shape, not a sound:

- `cymbal_roll(track, drum="cymbal", rate=(2, 8), low=0.3, peak=0.95)`: hits that get denser (hits per beat at the start,
  at the end; per second when `over` is seconds) and louder (velocity `low` to `peak`), stopping just before the target;
- `crescendo(track, pitches, low=0.3, peak=1.0, vel=0.8)`: a held note or chord tied to the target, its own `dynamics`
  rising from `low` to `peak`;
- `reverse_swell(track, pitch, peak=1.0, vel=0.8)`: one note swelling from silence to `peak`, ending exactly on the target;
- `sub_hit(track, pitch_or_drum, vel=1.0, dur=beats(2))`: a note (or, on a kit, a drum) struck on the target.

```python
marker("impact", at=bar(17))
build_to("#impact", over=beats(8), parts=[cymbal_roll(drums), crescendo(strings, ["D3", "A3", "F4"]),
                                          reverse_swell(pad, "D5"), sub_hit(low, "D1"), sub_hit(drums, "kick")])
```

Every note is written against the target in its own form (`"#impact-3.5beats"`, `bar(17) - beats(3.5)`), so moving the
marker moves the whole build. `over` is beats on a marker or a bar, or seconds on a marker or a seconds time; a bar with
seconds is refused (say the beats). The reply lists what each part wrote; edit or delete those notes like any other.
Listen to the result: a part sounds only as well as the instrument on its track plays held, swelling notes.

## Moments that read

A hit, a stop or a drop lands on time and still goes unheard when the music around it keeps going: a hit over a full bed
is only a little louder than the notes before it (and the limiter takes the rest), a band "stop" where the drums keep
playing is not a stop, drums 6 dB down are not "out". What makes a moment read is **contrast in time**: a little silence
before it, the other parts really stopping, a real gap. `moment(name, at)` writes that contrast onto the notes you have
already written, so the parts can be written straight through and the moment cut into them.

`m = moment("hit", at=31.5)` makes the marker `hit` (`at` is any time: seconds, `bar(17)`, `"#cue"`; leave `at` out to use
a marker already there) and returns the moment. Name it for what it is: markers named hit, stop, drums out, drums back,
climax or lift are read as asked moments by `render_mix`'s check, which then says whether it stands out. Then, on tracks:

| Action | What it does to the notes and hits written | Reads as |
|---|---|---|
| `m.rest(strings, basses, before=0.4)` | nothing starts in the 0.4 s before the moment; what is still sounding ends there | a breath, so the hit comes out of silence |
| `m.stop(band, until=37.5, short=0.2, release=0.05)` | what starts on the moment (within 30 ms) plays, cut to `short` s if given; what rings across it ends at the moment (+ `release`); nothing starts again before `until` (default: the song's end) | a band stop, a drop that is a gap, an ending |
| `m.choke(cymbals, after=0.25)` | what is sounding at the moment ends 0.25 s after it | a choked crash, the pedal lifted |
| `m.strike(brass, ["C2", "G2", "C3"], vel=1.0, ring=4.0)` | a note or chord on the moment, held `ring` s; on a kit `m.strike(drums, "crash")` (or a list of drums) adds hits | the layers of the hit itself |
| `m.swell(strings, over=4.0, low=0.5)` | what starts in the 4 s before the moment plays from 0.5x its velocity up to full | a run-up the hit lands on |

The actions run when the script ends, in the order written, on every note the script wrote (written before or after the
`moment` line). A cut keeps the note's own form: a length in beats stays in beats, seconds stay seconds, a tie ends at the
cut. `run_script`'s reply says what each did ("moment hit at 31.50 s: rest 0.40 s on strings, basses (3 notes dropped, 2
shortened); strike on brass (3 notes added)"): "nothing there to change" means the track had no notes near the moment.

A drum drop from 24.0 to 26.0 s is a stop with an `until`, then the drums come back on their own:

```python
out = moment("drums out", at=24.0)
out.stop(drums, until=26.0)              # a real gap, not quieter
back = moment("drums back", at=26.0)
back.strike(drums, "crash", vel=1.0)    # on top of the part's own kick at 26.0
hit = moment("hit", at=31.5)
hit.rest(pad, bass, before=0.5)          # the bed breathes out
hit.strike(low_brass, ["D1", "D2"], vel=1.0, ring=3.0)
hit.stop(pad, until=33.0)                # and stays out while the hit rings
```

The hit still has to be loud enough on its own: check it with `render_mix` (the check names a moment that does not stand out
and the track to tame).

## A loop that leads back into its start

A loop whose end meets its start must end on something that wants to go to the start's chord, and its length should be a whole
number of bars. Pick the length first: `bars = seconds * bpm / (60 * beats_per_bar)`; if that is not a whole number, change
the tempo so it is (`bpm = 60 * beats_per_bar * bars / seconds`, e.g. 30 s in 4/4 as 12 bars is 96 bpm), then `length(bar(bars + 1))`.
The last bar leads in by a chord that resolves to the first (a V chord, E7 to Am9, or a fill that stops where the first beat
starts), played by an instrument, and the last note ends before `length` (end it a beat early, or leave the ring-out room
inside `length`: the file is exactly that long). Check the join by rendering and reading `look_sound` (`what: "loudness"`,
`ending`): the last 0.5 s should be quiet enough, not cut.

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
vln.phrase(bar(5), bar(9), vel=[(0, 0.5), (1, 0.9)])  # velocity along the phrase, for notes that wrote no vel; louder is also brighter
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
  `dynamics` "Expression" and shows Sustain, Expression and Bend above the Editor's velocity strip. A note let go
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
- **Moving a section** (a one-off; in a script, change the section's times): `edit_document` `{"op": "section.move", "target": ["section.drop"], "args": {"by": {"beats": 8}}}`
  (or `"by": -2.5` seconds) moves the section and everything that starts inside it (notes, hits, clips, voice
  lines, tempo and key changes, other sections, automation points) in one undo step. A note, hit, clip or line
  nudged up to a 1/32 note before the section's line counts as inside (one that close to its end belongs to the
  next section), so humanised drums go along. **Markers stay** (they are
  sync points: a picture cut, "logo lands"), and so do the song's opening tempo, time signature and key; add
  `"markers": true` to move the song's own markers inside the section too. Each time keeps its form; a time on a
  marker that stays keeps the marker with a new offset. Effect envelopes inside effects don't move.
  A time signature change must stay on a bar line, so a section holding one moves by whole bars only (a move that
  puts it off a bar line is refused and names the nearest bar lines). In the arrangement: drag the section's bar. While
  you drag, the bar and a picture of the notes and clips inside it move with the pointer and nothing in the song
  changes; it lands on the nearest beat (Ctrl = exactly where you let go) and the chip names where ("bar 9.3"). It
  carries what was inside it when you pressed, never what it passes over, and lets go as one `section.move` (one
  undo step); Esc before letting go puts it back.
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
- **Drums.** The kits (`kit=`): `"drums"` (the default: a recorded rock kit), `"studio"` (a recorded studio kit), `"jazz"` (a recorded
  jazz kit played with brushes: brush snare, ride, soft hats and toms) and `"classic"` (synthesized). The recorded kits take
  `kick`, `snare`, `clap`, `hat`, `openHat`, `pedalHat`, `rim`, `tomLow`, `tom`, `tomHigh`, `crash`, `cymbal`, `ride`, `china`,
  `rideBell`, `splash`, `crash2`, `ride2`, `shaker`, and the jazz kit also `stir` (a brush swept round the snare: one hit
  under a bar or two; the other kits refuse it). A name a kit has no sample for is an error listing what it plays. The classic kit has
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
- Names (tones, reverb spaces, EQ shapes, effect types and fields, drum names): `inspect_engine` (compact; `name` for one thing). The plain instrument names and the kits, each with what it is: `inspect_guide 'agent-reference'`, "Instrument and kit names".
- Instruments installed on this machine: `inspect_library` (`find: "cello"`); the sample packs behind the plain names, installed or missing: `inspect_library (kind: packs)`, installed with `run_model_install`. What one can play: `inspect_engine` (`what: "instrument"`)
  (a note outside a sampled instrument's range fails the render and names the range).
- Ids: tracks are named by you; notes get ids from their track and start time (`strings.n1500`), so editing one note
  never renumbers the others.
- To change one value for good, change it in the script. `edit_document` (`track.set`, `note.set` …) is for a one-off touch-up:
  the history shows it as your edit, and the next script run keeps it, listed as held back.
