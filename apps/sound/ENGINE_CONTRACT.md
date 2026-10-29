# RostrumSound engine contract — `rostrum-sound-schedule/1`

How the Python side (and anything else) asks the Rust engine (`apps/sound/engine/`) for sound. The engine never owns the document (`shared/core/OPERATIONS.md` § 1): Python compiles the Sound document into a **schedule**, the engine renders it and answers with files and measurements.

The engine's code for this page lives in `engine/src/contract/`. Anything not on this page is refused.

## 1. Rules

1. **Versioned.** Every schedule starts with `"contract": "rostrum-sound-schedule/1"`. Another version is refused with the versions this engine reads.
2. **Unknown names fail loudly.** An unknown field, effect type, tone, reverb space, EQ shape, built-in instrument, drum name or note name is an error naming where it is and what is accepted. Nothing is silently replaced.
3. **Defaults are filled by the engine.** Only `id` and the content are required; everything else has the default given below. `check` returns the schedule with every default written in, so a caller can see what the engine will do.
4. **Times are seconds or beats, never sample indices.** A time is a number (seconds) or `{"beat": 8}` (beats from the start, through the tempo map). A length is a number (seconds) or `{"beats": 2}` (beats from where it starts).
5. **The engine decodes media itself:** a clip names a file (`media`) and an in-point (`in`). WAV, FLAC, OGG Vorbis, MP3 and the audio of MP4 / MOV files are read, resampled to the mix's rate and kept in a content-keyed cache.
6. **One request, everything back:** a render returns the mix, any stems asked for, and every track's meters at once.
7. **Errors** have the shared parts (`shared/mcp/CONVENTIONS.md` § 6): `code`, `where` (a path like `tracks[2].notes[5].pitch`), `subject`, `problem`, `accepted`, `hint`.

## 2. The schedule

```json
{
  "contract": "rostrum-sound-schedule/1",
  "sampleRate": 48000,
  "length": 20.0,
  "tempo": [{"beat": 0, "bpm": 96}],
  "master": {"loudness": -16, "truePeak": -1},
  "tracks": [
    {"id": "strings", "instrument": {"sfz": "C:\\...\\Violin Section.sfz"}, "volume": 0.8,
     "notes": [{"pitch": "D4", "at": {"beat": 0}, "dur": {"beats": 4}, "vel": 0.7},
               {"pitch": ["D3", "A3", "F4"], "at": 2.5, "dur": 1.0}],
     "effects": [{"type": "eq", "bands": [{"shape": "highpass", "freq": 80}]}]},
    {"id": "drums", "instrument": {"kit": "drums"},
     "hits": [{"drum": "kick", "at": {"beat": 0}}, {"drum": "snare", "at": {"beat": 1}, "vel": 0.7}]},
    {"id": "door", "clips": [{"media": "C:\\...\\door.wav", "in": 0.42, "length": 1.2, "at": 3.0, "volume": 0.6}]}
  ]
}
```

### Top level

| Field | Type | Default | Meaning |
|---|---|---|---|
| `contract` | string | required | `"rostrum-sound-schedule/1"` |
| `sampleRate` | 22050 … 192000 | 48000 | The mix's rate |
| `length` | time | the last note's end, ringing out | Where the music stops being played: nothing starting at or after it is heard, and a note held past it is let go there (with `ringOut`; without, it is cut). Not given: the song rings out from its last note's end until it has died away (−60 dBFS), up to 6 s; what still rings then fades out over its last 1.5 s |
| `ringOut` | bool | false | With a `length`: what still rings there (releases, decays, reverb) plays on until it falls under −60 dBFS, at most 6 s, and the file ends there; recorded clips stop at the length with a 50 ms fade. The render's `ending` and `warnings` say where it ended (`engine/src/contract/ending.rs`, added 2026-10-25) |
| `tempo` | number or list | 120 | A number (bpm), or tempo segments `[{"beat": b, "bpm": x}, …]` sorted by beat, the first at beat 0; tempo is constant inside a segment, or with `"ramp": true` glides evenly per beat to the next segment's bpm (exact: seconds = 60/k·ln(bpm/bpm₀), k bpm per beat; not on the last segment). The first segment may carry `"seconds": s` (≥ 0, default 0): the file time beat 0 starts at (the song's grid start); a time before it is a pickup, read back from beat 0 at the first tempo |
| `meter` | list | 4/4 throughout | The bar map the performance accents by: `[{"at": beat, "bar": beats in a bar, "beat": a main beat in beats}, …]`, the first at beat 0, in beat order (3/4: bar 3, beat 1; 6/8: bar 3, beat 1.5) |
| `master` | object | see below | The master bus |
| `tracks` | list | required (may be empty only with `length`) | Tracks, summed in this order |
| `buses` | list | `[]` | Buses tracks feed and send to (§ Buses and sends) |

### Track

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string `[A-Za-z0-9_.-]{1,64}` | required, unique | Names the track everywhere (meters, stems, errors, ducks) |
| `instrument` | object | none | What plays `notes` / `hits`; exactly one key, below. Required when the track has notes or hits |
| `notes` | list | `[]` | Pitched notes and chords |
| `hits` | list | `[]` | Drum hits |
| `clips` | list | `[]` | Recorded audio |
| `volume` | 0 … 4 (gain) | 0.85 | Fader |
| `pan` | −1 … 1 | 0 | Left … right |
| `reverb` | 0 … 1 | 0 | Send to the master's track reverb |
| `tone` | name | `"neutral"` | `neutral`, `muffled`, `warm`, `sub-boost`, `bright`, `voice-clarity`, `radio` |
| `mute` | bool | false | Rendered (so ducks can follow it) but not heard |
| `effects` | list | `[]` | Inserts after the tone, before the fader (§ Effects) |
| `automation` | object | none | `{"volume": [[time, gain], …], "pan": [[time, pan], …]}`, points in time order; replaces `volume` / `pan` where set |
| `ducks` | list | `[]` | Dips under other tracks (§ Ducks) |
| `output` | bus id | none (the master) | The bus this track feeds instead of the master (§ Buses and sends) |
| `sends` | list | `[]` | Copies of the track into buses (§ Buses and sends) |
| `expression` | object | none | CC-style dynamics and vibrato lanes (§ Track expression) |
| `perform` | `true`, `false` or object | `true` | How the notes and hits are played (§ Perform): `true` the instrument family's defaults, an object merged over them, `false` exactly as written |

### Instrument (one key)

| Form | Meaning |
|---|---|
| `{"builtIn": "piano"}` | A plain name (§ Plain names): a recorded instrument, an analog synth preset, or `classic.<voice>` for a synthesized one |
| `{"sfz": "<path>", "legato": false, "swell": false, "velocityTone": 12}` | A sampled instrument (SFZ file). A note outside its samples fails and names the range. `velocityTone` (dB, 0 … 48; 0 off): on a key the file recorded in fewer than three velocity layers, a note gets a 2.5 kHz high shelf of −`velocityTone` × (1 − velocity) dB, so it brightens as it is played harder, like a many-layered instrument (`instruments/sfz/tone.rs`, added 2026-10-28). Keys with three layers or more play as recorded; recorded kits and the organs have it off |
| `{"kit": "drums", "even": false}` | `even` (added 2026-10-25): each piece at its measured starting level against the kick and snare (`engine/data/kit_levels.json`, `describe` › `kits` › `evenLevelsDb`) and each sample's first milliseconds held within 15 dB of its hit's loudness (`instruments/sfz/tame.rs`). A drum kit: `drums` (recorded rock kit), `studio` (recorded studio kit) or `classic` (the synthesized kit: `kick`, `snare`, `clap`, `hat`, `openHat`, `cymbal`, `tom`, `rim`). `synth` is no longer a kit name (documents open it as `drums`) |
| `{"kitSfz": "<path>"}` | An SFZ drum kit on General MIDI keys; hits name a GM drum or a key number |
| `{"model": "guitar", "position": 0.13, "damping": 0, "hardness": 0.5}` | A procedural instrument (§ 2a): `guitar`, `nylonGuitar` (plucked strings), `marimba`, `vibraphone`, `glockenspiel`, `tubularBell` (struck bars), `violin` (a bowed solo voice, learned model). The touch fields are the track's defaults; a note may override them |
| `{"synth": "saw", "attack": 0.3, "brightness": 2400, …}` | A subtractive synth (§ 2a): the value is the wave (`saw`, `square`, `triangle`, `sine`) |
| `{"plugin": {"format": "clap", "path": "C:\\…\\Synth.clap", "id": "<id>", "params": {…}, "state": "<base64>"}}` | A CLAP / VST3 instrument plugin (§ Plugins). One instance plays all the track's notes (its own polyphony and releases) |

An `sfz` instrument may also name **articulations**: `{"sfz": "<sustain.sfz>", "articulations": {"spiccato": "<spic.sfz>", "tremolo": "<trem.sfz>"}}`. A note picks one with `"art": "spiccato"`; without `art` it plays the main file. This is the keyswitch for libraries that ship one file per playing style (VSCO 2, most CC0 libraries); SFZ files with `sw_*` keyswitch opcodes are still refused with that message.

### Plain names (added 2026-10-25: recorded instruments, Sam's choice by ear)

The plain names are the `builtIn` names; the table is `engine/src/contract/names_instruments.rs` and `describe` answers it (`instruments`, each with what it plays, `about`, `pack`, `range`, `articulations` (the first plays by default), `family`, `credit`, `installed`). A document keeps the name as written; the engine resolves it when it plays.

- **Recorded** (packs under `<assets>/sounds/<pack>/`; `<assets>` is `ROSTRUM_ASSETS_DIR`, else `%USERPROFILE%\.rostrum\assets`): `piano`, `grandPiano`, `acousticPiano`, `feltPiano` (Salamander concert grand, CC-BY: credited); `electricPiano`, `wurlitzer` (Wurlitzer EP200, CC-BY: credited); `rhodes` (Fender Rhodes Mark II by Tim Kahn, Freesound, CC-BY 4.0: credited; F4–C#6 stretched from E4 and D6, crossfaded over B4–G5); `organ`, `drawbarOrgan` (FreePats drawbar organ), `pipeOrgan` (VCSL); `guitar`, `nylonGuitar` (FreePats Spanish classical guitar, a SoundFont); `acousticGuitar`, `steelGuitar`, `archtopGuitar` (Karoryfer Shinyguitar); `electricGuitar`, `cleanGuitar` (FreePats FSBS clean); `bass`, `electricBass`, `bassGuitar` (Karoryfer Growlybass, A0–G4: the pack names each sample an octave above what it sounds; the table's `key_offset` plays it at the pitch written); `uprightBass`, `doubleBass` (D. Smolken, pizzicato); `strings`, `analogStrings` (a VSCO 2 string section split by pitch: basses below C2, cellos to B2, violas to F#3, violins above; sustain) and `spiccatoStrings` (the same, spiccato); `violins`, `violas`, `cellos`, `basses`, `violin`, `harp` (VSCO 2); `cello` (Karoryfer x bigcat solo cello); `brass`, `cinematicBrass` (a VSCO 2 brass section split by pitch: tuba to D2, trombone to D4, trumpet above, each zone level-matched at its seams; changed 2026-10-28, the horn played A#3–A#4 from one soft take); `horn`, `trumpet`, `trombone`, `tuba` (VSCO 2); `mutedTrumpet` (the trumpet in its `muted` articulation: a straight mute); `flute`, `piccolo`, `oboe`, `clarinet`, `bassoon` (VSCO 2); `saxophone`, `tenorSax` (VCSL); `harmonica` (Hohner Super 64 chromatic, VCSL); `marimba`, `glassMarimba`, `vibraphone`, `xylophone`, `glockenspiel`, `tubularBells` (VCSL); `timpani` (VSCO 2).
- **Analog synth presets:** `warmPad`, `pad` (analog pad), `subBass` (analog bass), `pluck` (analog pluck).
- **Classic synthesized voices:** `choirPad` (no permissive recorded choir exists), and every old voice by `classic.<name>`: `classic.feltPiano`, `classic.grandPiano`, `classic.warmPad`, `classic.analogStrings`, `classic.spiccatoStrings`, `classic.choirPad`, `classic.cinematicBrass`, `classic.subBass`, `classic.glassMarimba`.

Every sampled note (SFZ, recorded instruments, kits) starts early by its sample's attack, so it is heard on its time (added 2026-10-25, `instruments/sfz/onset.rs`): the attack is the time from the region's start until the sample's 10 ms RMS comes within 12 dB of the loudest it gets in its first half second, plus the region's `ampeg_delay`, at most 0.15 s; a legato note (entering past its attack) does not lead; a note in the song's first moments starts at 0 and is as late as its attack. The note is still let go at its written end. `range` answers `attackMs` (`typical`, `most`) for an SFZ instrument.

A recorded instrument's note may name an articulation with `art` (`"spiccato"`, `"pizzicato"`, `"staccato"`, `"muted"`, …, as `describe` lists them; an instrument with a `sustain` also plays `legato` and `swell` on it). A plain name whose pack is missing is a loud `NOT_FOUND` error naming the instrument, the pack and the install step (`Install it: python -m rostrum_sound.packs install <pack> (an agent: run_model_install with "<pack>")`), never silence or a synth instead. A render answers `credits`: the distinct credit lines of the CC-BY instruments it played (every export carries them); `check` answers them too.

**Kits** (`describe` › `kits`): `drums` (MuldjordKit, CC-BY: credited; rim, clap and shaker from the studio kit), `studio` (Karoryfer Big Rusty Drums + VCSL claps and shaker, CC0), `jazz` (Karoryfer Swirly Drums, played with brushes, CC0; rim, clap, shaker and ride bell from the studio kit), `classic` (synthesized). The recorded kits answer to one list of hit names (`gmDrums`): `kick`, `kick2`, `rim`, `snare`, `clap`, `snare2`, `hat`, `pedalHat`, `openHat`, `lowTom`, `floorTom`, `tomLow`, `tom`, `midTom`, `tomHigh`, `highTom`, `crash`, `cymbal`, `ride`, `china`, `rideBell`, `splash`, `crash2`, `ride2`, `stir` (key 60: the jazz kit's brush stir), `shaker`. A name or key the kit has no sample for is an error listing what it plays.

### Perform (added 2026-10-25: the performance layer, on by default)

A track's notes and hits are played, not just sequenced: each note lands up to ± `timing` ms off the grid, `lean` lays the whole part back (+ ms) or pushes it (−), `swing` (0 … 1) makes the off-beat `swingGrid` cells (0.5 = 8ths, 0.25 = 16ths) late, `velocity` (± fraction) varies each note, `dynamics` `[[time, factor 0 … 2], …]` shapes the part, `accent` (0 … 0.5) lifts notes on the beat (the bar's downbeat, 4 beats, by all of it, the others by half), `articulation` (`legato`: a note joins the next when only a breath, < 0.15 s, separates them; `staccato`: shortened; `normal`) applies to notes without their own `art`, `vibrato` `{"rateHz", "depthCents", "delaySec": 0.2}` or `false` goes on held notes (0.3 s or more) that have no vibrato of their own, `pedal` (`true`, `false` or `[[from, to], …]` times) holds notes to the range's end, `strum` (0 … 1) varies a strummed chord's gaps string to string and makes each string a little softer, `seed` (any number) picks another, still repeatable, performance. Seeded by the track id: the same every render. `person` (`true` by default; added 2026-10-25): `false` turns the family's looseness off (its `timing`, `velocity`, `accent`, `strum`, `articulation` defaults become 0 / `normal`) while every field named beside it still plays, so `{"person": false, "swing": 0.5}` swings a machine-tight part. `perform: false` still plays everything exactly as written, swing included. No voice moves before 0 or past a given `length`.

Defaults by family (`describe` › `perform`): plucked {timing 8, velocity 0.12, accent 0.07, strum 0.6}; mallets {6, 0.12, 0.08}; drums {4, 0.1, 0.06}; sustained {10, 0.08, 0.04, articulation legato}; detached {6, 0.1, 0.06}; keys {6, 0.1, 0.05}; synth {velocity 0.05}; the rest 0 (`lean`, `swing`, `dynamics`, `vibrato`, `pedal` off). The family: a recorded instrument's from its default articulation (`keys`, `pedal` keys; `spiccato`, `staccato`, `tremolo` detached; `pizzicato`, `pluck`, `fingerstyle` plucked; `hit`, `roll` drums; `mallet` mallets; any other sustained); kits drums; synth presets and `synth` synth; models guitar / nylonGuitar plucked, bars mallets, violin sustained; classic voices feltPiano / grandPiano keys, glassMarimba mallets, spiccatoStrings detached, the others synth; `sfz` files and plugins keys. Recorded clips are never performed.

### 2a. Instrument settings (added 2026-10-21, P4)

| Form | Field | Range | Default | Meaning |
|---|---|---|---|---|
| `model` | `position` | 0 … 0.5 (strings play at least 0.03) | the instrument's own (guitar 0.13, nylonGuitar 0.2, marimba 0.42, vibraphone / glockenspiel 0.4, tubularBell 0.05) | Where it is plucked or struck: bridge / bar end (0) … middle (0.5). Not for `violin` |
| `model` | `damping` | 0 … 1 | 0 | Plucked strings only: 0 rings open … 1 palm-muted |
| `model` | `hardness` | 0 … 1 | 0.5 | Pick / mallet: soft … hard. Not for `violin` |
| `synth` | `voices` | 1 … 16 (whole) | 3 | Oscillators per note (detuned) |
| `synth` | `detune` | 0 … 100 cents | 12 | Spread of the voices |
| `synth` | `brightness` | 40 … 20000 Hz | 2400 | Filter cutoff |
| `synth` | `resonance` | 0 … 1 | 0.2 | Filter resonance |
| `synth` | `envAmount` | 0 … 8 octaves | 0 | How far the filter opens with the envelope |
| `synth` | `attack`, `decay`, `release` | 0.001 … 20 s | 0.3, 0.5, 0.8 | The envelope |
| `synth` | `sustain` | 0 … 1 | 0.8 | The envelope's held level |
| `synth` | `octave` | −3 … 3 (whole) | 0 | Octave shift |
| `synth` | `drive` | 0 … 10 | 0 | Saturation after the filter |
| `synth` | `width` | 0 … 1 | 1 | Stereo spread of the voices |
| `synth` | `drift` | 0 … 30 cents | 0 | Analog wander |
| `synth` | `noise`, `sub` | 0 … 1 | 0, 0 | Noise and a sine an octave below |

### Note

| Field | Type | Default | Meaning |
|---|---|---|---|
| `pitch` | `"D4"`, `"F#3"`, `"Bb2"`, a MIDI number, or a list of those (a chord) | required | C4 = MIDI 60 |
| `at` | time | required | Start |
| `dur` | length | required | How long it is held (the release rings after it) |
| `vel` | 0 … 1 | 0.8 | Velocity |
| `pan` | −1 … 1 | 0 | Within the track |
| `art` | an articulation name of the track's `sfz` | none (the main file) | Playing style (see Instrument) |
| `position`, `damping`, `hardness` | as the `model` form | the track's | The touch of this note (`model` tracks only) |
| `dynamics` | `[[fraction 0 … 1, level 0 … 2], …]` | none | The note's own swell / fade across its length (fraction of `dur`), straight lines between, multiplied into its level |
| `vibrato` | `{"rate": 5.5, "depth": 20, "delay": 0.2}` (Hz, cents, seconds) | none | Steady vibrato, fading in over a quarter second after `delay` |
| `bend` | `[[seconds into the note, cents], …]` | none | Pitch bend (a slide, a fall, a scoop) |
| `strum` | −200 … 200 ms | 0 | A chord's tones one after another, this far apart (low to high; negative: from the top), each held to the chord's end |

### Track expression (CC-style lanes; added 2026-10-21, P4)

A track may carry `expression`: `{"dynamics": [[time, level 0 … 2], …], "vibrato": [[time, amount 0 … 1], …], "vibratoRate": 5.5, "vibratoDepth": 25}`. Times are times (seconds or beats). Like a MIDI player's CC 11 (expression) and CC 1 (mod wheel): the lanes run across notes, straight lines between points, held before the first and after the last. `dynamics` multiplies every note's level (with the note's own `dynamics`); `vibrato` is the mod wheel, 1 = `vibratoDepth` cents at `vibratoRate` Hz, 0 = none (a note's own `vibrato` adds to it). Works on every pitched instrument (sampled, built-in, synth, model).

Added 2026-10-23 (S56): `"sustain": [[time, 0 … 1], …]` is the pedal (CC 64): a note whose end falls while it is 0.5 or more rings on until it next drops below 0.5 (a pedal never lifted lets go at its last point); the note's resolved `dur` stays as written. `"bend": [[time, -1 … 1], …]` is the pitch wheel, 1 = up `bendRange` semitones (0 … 24, default 2), added to a note's own `bend`. A step is two points at one time. A track with none of these plays exactly as before.

### Hit

| Field | Type | Default |
|---|---|---|
| `drum` | name or GM key | required |
| `at` | time | required |
| `vel` | 0 … 1 | 0.85 |
| `pan` | −1 … 1 | 0 |
| `tune` | 0.25 … 4 (pitch ratio; `classic` kit only) | 1 |
| `decay` | 0.1 … 4 (factor of the hit's length) | 1 |

### Clip (recorded audio)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `media` | path | required | The file; the engine decodes it |
| `in` | seconds ≥ 0 | 0 | In-point inside the file |
| `length` | length | to the file's end | How much of the file plays (the file's own time, before `pitch` and `stretch`; a length in beats is counted from `at`). On the timeline the clip lasts `length` ÷ 2^(`pitch`/12) × `stretch` |
| `at` | time | required | Where it starts in the mix |
| `volume` | 0 … 4 | 1 | Clip gain |
| `pitch` | −24 … 24 semitones | 0 | Played like tape (pitch changes speed and length) |
| `stretch` | 0.25 … 4 | none | Length factor with the pitch kept: 2 plays twice as long, 0.5 twice as fast. Applied after `pitch` |
| `shift` | −24 … 24 semitones (fractions are cents) | none | Pitch change with the length kept. Adds to `pitch` |
| `pan`, `panTo` | −1 … 1 | 0, = `pan` | Pan, moving from `pan` to `panTo` over the clip |
| `fadeIn`, `fadeOut` | seconds ≥ 0 | 0 | Equal-power fades |
| `reverb` | 0 … 1 | 0 | The clip's own reverb send |
| `effects` | list | `[]` | Inserts on this clip only |

### Effects

Every effect is `{"type": <name>, …}`. A parameter marked *env* takes a number or an envelope `[[time, value], …]`.

| `type` | Fields (default) |
|---|---|
| `eq` | `bands`: list of `{"shape", "freq", "gain" (0 dB), "q" (0.707)}` (*env* each); shapes `lowshelf`, `highshelf`, `peak`, `lowpass`, `highpass`, `notch` |
| `compressor` | `threshold` (−18 dB, *env*), `ratio` (3, *env*), `attack` (0.01 s), `release` (0.15 s), `makeup` (0 dB, *env*), `knee` (6 dB) |
| `reverb` | `space` (`hall`; `dry`, `room`, `hall`, `cathedral`, `shimmer`, `freeverb.room`, `freeverb.hall`, `freeverb.cathedral`), `mix` (0.25, *env*); `decay` (s), `damping`, `size` (0 … 1) only for `freeverb.*` |
| `delay` | `time` (0.375 s), `feedback` (0.35, *env*), `mix` (0.2, *env*), `pingPong` (false), `damp` (0.3) |
| `saturate` | `drive` (0.3, *env*), `mix` (1, *env*) |
| `tape` | `wow`, `flutter`, `age` (0.2 each, *env*); `hiss`, `crackle` (0 each, *env*: a record's surface, absolute levels, drawn apart on each channel) |
| `limiter` | `ceiling` (−1 dB), `release` (0.1 s) |
| `width` | `width` (1; 0 mono, 2 wider, *env*), `monoBelow` (120 Hz) |
| `chorus` | `rate` (0.8 Hz), `depth` (0.5, *env*; ±5 ms sweep at 1 around 12 ms), `mix` (0.5, *env*; 1 = only the swept copy), `spread` (1: the right sweep half a turn behind the left; widens a mono source). Per left/right pair (`fx/chorus.rs`, added 2026-10-28) |
| `tremolo` | `rate` (4 Hz), `depth` (0.5, *env*), `stereo` (0: both sides together; 1: opposite, an auto-pan whose two gains sum to one). Per left/right pair (`fx/tremolo.rs`, added 2026-10-28) |
| `gate` | `threshold` (−45 dB), `ratio` (4), `range` (30 dB), `attack` (0.002 s), `hold` (0.05 s), `release` (0.12 s) |
| `deess` | `freq` (6000 Hz), `threshold` (−30 dB), `range` (8 dB) |
| `dehum` | `freq` (0 = found in the clip; else 50 / 60), `harmonics` (6), `width` (40) |
| `dereverb` | `amount` (0.5: how much of the modelled late reverb is taken out), `reduction` (18 dB at most), `time` (0 = the room's decay time measured from the clip, else RT60 in s). Statistical late-reverb suppression, no model (`dialogue/dereverb.rs`); offline only (not on live play) |
| `plugin` | `format` (`clap` / `vst3`), `path`, `id`, `params` ({}), `state` (none): a CLAP / VST3 effect plugin (§ Plugins) |

Clip `stretch` and `shift` (added 2026-10-21, P8) use the engine's stretcher (Signalsmith Stretch for music, PSOLA when the engine hears a voice in the clip); both may be set together, and with `pitch`. `check` writes `null` for the ones not set.

### Sounds made from settings (removed 2026-10-23)

Rostrum no longer makes sounds from settings (Sam, 2026-10-23, PURPOSE.md): movement is scored with instruments
(notes, chords and drum hits on ordinary tracks) or with real recordings as clips. The Python side never writes a
track's `sounds` list. An older song that still has one opens, and says so in plain words on the Problems chip, in
`inspect` and in every agent reply, naming the sound, its time and its track, for example: *fx: this song has a
designed sound ("riser" at 2 s) that Rostrum no longer makes; it is left out of the mix. Replace it with an
instrument*. It stays in the file and is never sent to the engine.

### Plugins (added 2026-10-21, P8)

A plugin is `{"format": "clap" | "vst3", "path": "<absolute path to the .clap file or .vst3 bundle>", "id": "<the plugin's id in that file>", "params": {…}, "state": "<base64>"}`: as an effect, these fields with `"type": "plugin"`; as an instrument, inside `{"plugin": {…}}`. The engine loads the plugin once to check it (kept per file and modified time), so each of these fails naming where it is: a format other than `clap` / `vst3`; a path that is not absolute, does not exist or has the other format's extension; an id the file does not hold (the ids it holds are listed); an instrument plugin in an effect slot, or an effect plugin as an instrument; a parameter the plugin does not have (with "did you mean"); a value outside the parameter's range; a `state` that is not base64.

| Field | Default | Meaning |
|---|---|---|
| `format` | required | `clap` or `vst3` (VST3 on Windows only) |
| `path` | required | The `.clap` file or `.vst3` bundle |
| `id` | required | The plugin's id inside the file, as the `plugins` request lists it (a CLAP id like `org.surge-synth-team.surge-xt`; a VST3 class id in hex) |
| `params` | `{}` | `{"<parameter id or name>": value}`. A value is a number in the parameter's range (CLAP: the plugin's own range; VST3: 0 … 1, normalized) or an envelope `[[time, value], …]` (times are seconds or beats). A name two parameters share is refused: use the id. `check` keys them by id |
| `state` | none | The plugin's saved state (its own bytes, base64), as `pluginWindow` answers it. Loaded first, so `params` win over it |

A plugin instrument is sent notes only: a note's `pan`, `dynamics`, `vibrato`, `bend` and the track's `expression` lanes are refused on its track (pan the track; use the plugin's own parameters). A track render with a plugin is cached like any other (the key holds the plugin file's stamp, its state and its parameters).

### Ducks

`{"under": ["voice"], "depth": 0.5, "attack": 0.02, "release": 0.3, "lookahead": 0.01, "hold": 0.0, "voice": false}`: the track dips by up to `depth` (0 … 1 of its gain) while the named tracks sound. `voice: true` keeps the bass and lets the music swell back (for dialogue).

### Buses and sends (added 2026-10-21, P5)

A bus: `{"id": "verb", "volume": 1, "pan": 0, "mute": false, "effects": […], "automation": {"volume": […], "pan": […]}, "output": "<bus id>"}`. It sums what feeds it, runs its `effects` (the same inserts as tracks), then its fader and pan, then goes to the master, or to another bus named by `output`. Bus ids follow the track id pattern and differ from every track id; an `output` that loops back (`a → b → a`) is refused, naming the loop.

A track's `output` names the bus it feeds instead of the master. Its `sends`: `[{"bus": "verb", "level": 0.3, "pre": false}]`, a copy of the track into a bus; `level` 0 … 4 is a number or an automation lane `[[time, level], …]`; `pre: true` takes the copy before the track's fader (and its volume lane). A send to the bus the track already feeds is refused (it would play twice).

The render answer adds `buses` (per bus: `id`, `peak`, `rms`, `lufs`, measured after its fader). A stem is still its track's own output; with stems asked for, each bus is also written as `<bus>.bus.wav` (`busStems`, after its effects and fader), and `direct` lists the tracks that play straight to the master: their stems plus the bus stems add up to the mix before the master bus (P10, checked to 3e-8). Ducks stay on tracks: to duck a music bus under the voice, duck each track feeding it.

### Master

| Field | Default | Meaning |
|---|---|---|
| `volume` | 1 | Master fader |
| `automation` | none | `{"volume": [[time, gain], …]}` |
| `reverb` | `"dry"` | The master bus' reverb (a space name) |
| `trackReverbSpace` | `"hall"` | The space the tracks' `reverb` sends go to |
| `fadeIn`, `fadeOut` | 0 s | Fades of the whole mix |
| `effects` | `[]` | Master inserts, before mastering |
| `loudness` | null | Integrated loudness target (LUFS); null leaves the level as mixed |
| `truePeak` | −1 | True-peak ceiling (dBTP) |
| `glue` | 0 | Glue compression 0 … 1 |
| `maxLimit` | null | The most the limiter may pull (dB, 0 … 24); a mix that would need more is turned down as a whole (one gain), landing under its target; the render's `master.heldDb` says by how much. null: the limiter pulls as hard as it must |
| `safetyClip` | true | The last soft clip above −1 dBFS |

## 3. Requests

Two ways in, the same requests and answers:

- **Long-lived process (the app's way):** `rostrum-sound serve`. One JSON request per line on stdin, one JSON answer per line on stdout, matched by `id`. Instruments, samples and decoded media stay loaded between requests, and each track's render is cached by its content, so a re-render after a small edit only renders the tracks that changed. `{"do": "quit"}` ends it.
- **One shot:** `rostrum-sound request <request.json>` answers one request and exits; `rostrum-sound render <schedule.json> <out.wav>` is short for a render request.
- Engine work only: `rostrum-sound render-job <job.json> <out.wav>` renders the internal job (`engine/src/mix/schedule/`) the contract compiles to. `play` (the live transport) still takes the internal job; it moves to the contract with the Sound screen.

Every answer is `{"id": …, "ok": true, "result": {…}}` or `{"id": …, "ok": false, "error": {…}}`. A failed render writes nothing under its output name (it renders to `<name>.partial` first). A render's files are whole once the mix has its name: its levels file is put beside it first (written to `.partial` and renamed too), and the mix takes its name last, in one rename that replaces an older file (the name never points at nothing). The answer is the announcement: read a render's path from the answer, never by waiting for the file to appear.

| `do` | Fields | Answer |
|---|---|---|
| `describe` | — | `contract`, `engine` (version), `requests` (every `do` this engine answers; added 2026-10-27 with `measure`), and every accepted name: `tones`, `spaces`, `eqShapes`, `effects` (each with its fields and defaults), `builtIns` (every `builtIn` name), `instruments` (each plain name: what it plays, § Plain names), `kitNames`, `kits`, `perform` (`families`: each family's defaults; `articulations`: an articulation's family), `synthDrums`, `gmDrums`, `mediaFormats`, `pluginFormats`. Installed plugins are not listed here (that loads each one): ask `plugins` |
| `check` | `schedule` | The schedule with every default filled in and every time in seconds (`resolved`), plus `length`, `tracks` count and `credits`. Nothing is rendered |
| `render` | `schedule`, `out` (WAV path), optional `stems` (`"all"` or a list of track ids), `stemsDir` (default: beside `out`, named `<out stem>.stems`), `master` (true; false skips mastering), `from` / `to` (seconds, both or neither: the file is that stretch of the song; tracks render whole and stay cached, the master stage, its loudness target and the file's measures work on the stretch alone, stems are cut to it; P29), `inSong` (with `from` / `to`; true: the stretch as it is in the whole song's render, sample for sample: the master works it out over the song and the stretch is cut from it), `masterAs` (with `from` / `to`; `{program, gainDb, heldDb}`, a reply's `decisions`: the stretch as the song mastered with those decisions has it, rendered on its own: the master stage runs from 3 s before it, a track not in the cache renders only from 3 s before that and only its notes heard there, and is not cached; a song with time warps, a whole-take master insert, a loop's wrap or ducks renders whole as `inSong` does; added 2026-10-29) | `decisions` (the whole song's mastering decisions `{program, gainDb, heldDb}`, with a master, for a whole render or an `inSong` / `masterAs` stretch), `windowed` (true: the stretch rendered on its own), `file`, `seconds` (the song's), `credits` (the CC-BY instruments' credit lines), `range` (`[from, to]` in seconds as rendered, `to` held at the song's end; null without), `renderSeconds`, `ending` (with a `length`: `{length, end, ringOut, levelAtLengthDb, heldPastLength, cut}`; `seconds` is `end`), `warnings` (plain words: a ring-out past the length, a cut ending, notes held past it), `lufs`, `truePeak`, `peak`, `lra`, `clipped`, `bands`, `series` (short-term loudness, true peak and stereo correlation every 100 ms), `tracks` (per track: `id`, `peak`, `rms`, `lufs`, `span`, `onsets`, `bands`), `stems` (`{id: path}`), `busStems` (`{bus id: path}`, when any stem is asked for and there are buses), `direct` (track ids), `ducks` (where each duck dipped) |
| `measure` | `schedules` (a list of schedules: trials, answered in order; or one `schedule`), optional `master` (true) | `results`: per schedule the numbers a `render` of it answers (`lufs`, `truePeak`, `peak`, `renderSeconds`, `master` `{gainDb, glueMaxReductionDb, limiterMaxReductionDb, heldDb}`, `tracks` and `buses` with `id`, `peak`, `rms`, `lufs`), and `renderSeconds` for all. Nothing is written. For searches over many versions of one song (the host's loudness fit): the same mix and master as `render`, bit for bit, but each track's instrument render and each unchanged track's measures are held in memory from one `measure` to the next (any other request lets them go; at most 1 GB of instruments), up to 4 trials of one request mix side by side, and a short song's mastering passes stay in memory. Added 2026-10-27 |
| `range` | `instrument` (as in a track) | `instrument` (as resolved; a plain name is read as a track reads it, so a missing pack is the same error), `low`, `high` (note names), `lowKey`, `highKey` (MIDI), `gaps` (keys inside the range with no sample), `layers` (velocity layers), `drums` (names a kit answers to), `attackMs` (an SFZ instrument: `{typical, most}` ms its notes start early, one per sample at velocity 100; else null) |
| `plugins` | optional `path` (a `.clap` / `.vst3`, or a folder, searched 4 levels deep) | Without `path`: the standard folders (`CLAP_PATH`, `VST3_PATH`, `%LOCALAPPDATA%\Programs\Common\CLAP` and `…\VST3`, `C:\Program Files\Common Files\CLAP` and `…\VST3`) and `%USERPROFILE%\.rostrum\assets\plugins`. Answers `folders` (searched), `plugins` (each: `format`, `path`, `id`, `name`, `vendor`, `kind` (`effect` / `instrument`), `hasWindow`, `params`: `[{id, name, min, max, default, steps?, unit?, plainMin?, plainMax?}]`; `steps` only on stepped parameters; `plainMin` / `plainMax` the VST3 range the 0 … 1 value stands for) and `failed` (files that would not load, each with its `error`). Each plugin is loaded in the engine's own process to read it |
| `pluginWindow` | `plugin`: a plugin (§ Plugins; `params` and `state` optional) | Opens the plugin's own window for a person and answers when they close it: `state` (base64, for the document), `params` (`{id: value}`: the current values of the parameters the request named; everything else is in `state`), `errors` (anything the plugin reported meanwhile). Nothing else is answered while the window is open. The window runs in its own process (`rostrum-sound plugin`), so a plugin crash fails the request (`JOB_FAILED`), not the engine |

Files: the mix and the stems are 32-bit float WAV at `sampleRate`, stereo. A stem is its track as it reaches the master (after its effects, fader and ducks), then through the master's whole gain: master fader and its lane, fades, glue, the gain to the loudness target and the limiter, the gain the mix took at each frame (worked out once on the mix, `fx/master.rs` Dynamics, `mix/mastergain.rs`), before master effects, master reverb and the safety clip. So the stems add up to the mix wherever those did not act. The render answer carries `master`: `{gainDb, glueMaxReductionDb, limiterMaxReductionDb, heldDb, insertsOnMix, onMixOnly, stemsMaxDifference}` (`onMixOnly`: what the stems cannot carry, in words, empty normally; `stemsMaxDifference`: the largest |sum of stems − mix| sample, measured when the stems hold everything that reaches the master, else null), `stemMeters` / `busStemMeters` (each stem file as written: `lufs`, `truePeak`, `peak` dB, `overFullScale` samples, `lastAudible` frame) and `series.reductionDb` (the glue and limiter's deepest reduction per 100 ms, dB ≥ 0). Meters are measured on the same signal.

### Live meters: `<out>.levels.json` and `rostrum-sound play` (added 2026-10-23, H62)

Every `render` also writes `<out stem>.levels.json` beside the mix: each track's, each bus' and the master's peak and RMS per 1/30 s window, measured on the same signals as the answer's meters (a track or bus as it reaches the master, the master as the file holds it), in the file's time. `{"contract": "rostrum-sound-levels/1", "mix": {"bytes", "modified"}, "hop": 0.0333, "strips": {"<track id>" | "<bus id>" | "master": [peak, rms, peak, rms, …]}}`, values in tenths of a dB (−1200 = silence). `mix` is the WAV's size and modified time when it was written: a levels file for another render of the same name is refused. `rostrum-sound play <mix.wav>` (the live transport, `engine/src/live/play.rs`) reads it for the file it plays and for every `{"load"}`, and while the mix rolls prints `{"levels": {"t": <mix seconds at the speaker>, "strips": {"<id>": [peakDb, rmsDb], …, "master": [peakDb, rmsDb]}}}` about 30 times a second (each strip's loudest window since the previous line, so no peak is skipped), and `{"levels": null}` once when it stops. Without a levels file it prints one `{"error": "meters: …"}` line and no levels: they are never guessed.

**Starting and loading** (changed 2026-10-27): `{"rolling": t}` is printed when the first played block reaches the speaker (the device's clock; within 5 ms), so a playhead started on it starts with the sound; before, it came when the block was written, an output delay early (~10 ms on speakers, ~250 ms on Bluetooth headphones). A device with no clock gets it 1 s after the play, as before. A `{"load": <file>}` is read on its own thread: commands after it (a Play, a Stop) are not held up, play goes on with the render it has, and the new one is swapped in at the playhead once it is read (only the newest of several waiting is read; one that cannot be read prints `{"error"}` and the last one plays on). A Play while recording is armed waits for the newest load, so a take is played against the song as it is now. The engine's own 32-bit float render is read once straight into frames (a 3-minute song: ~70 MB).

## 4. How far this version goes (2026-10-21)

- Done: everything above.
- Not in version 1 yet (the engine can do them; a later version adds them to the contract): surround beds and objects, speed ramps and warp markers, formant control, time warps, glitch, filter sweeps, reverse, spectral repair, tone match, plugin presets and MIDI controller lanes to plugins, the procedural drum kit (`model.kit`), speech. (Note expression, articulations, the procedural instruments and the synth were added on 2026-10-21, P4; buses and sends on 2026-10-21, P5; clip `stretch` / `shift`, CLAP / VST3 effects and instruments and the `plugins` / `pluginWindow` requests on 2026-10-21, P8. Each addition only adds optional fields and requests, so the contract name stays `rostrum-sound-schedule/1`.)
- Not done: progress lines during a long render, and rendering only the changed part of a track (today the smallest unit that re-renders is a whole track).
