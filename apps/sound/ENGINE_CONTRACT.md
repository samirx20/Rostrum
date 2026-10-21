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
    {"id": "drums", "instrument": {"kit": "synth"},
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
| `length` | time | end of the last sound + 2 s | How long the mix is; nothing past it is heard |
| `tempo` | number or list | 120 | A number (bpm), or tempo segments `[{"beat": b, "bpm": x}, …]` sorted by beat, the first at beat 0; tempo is constant inside a segment |
| `master` | object | see below | The master bus |
| `tracks` | list | required (may be empty only with `length`) | Tracks, summed in this order |

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

### Instrument (one key)

| Form | Meaning |
|---|---|
| `{"builtIn": "grandPiano"}` | A synthesized instrument: `feltPiano`, `grandPiano`, `warmPad`, `analogStrings`, `spiccatoStrings`, `choirPad`, `cinematicBrass`, `subBass`, `shepardRiser`, `glassMarimba` |
| `{"sfz": "<path>", "legato": false, "swell": false}` | A sampled instrument (SFZ file). A note outside its samples fails and names the range |
| `{"kit": "synth"}` | The engine's synthesized drum kit: `kick`, `snare`, `clap`, `hat`, `openHat`, `cymbal`, `tom`, `rim` |
| `{"kitSfz": "<path>"}` | An SFZ drum kit on General MIDI keys; hits name a GM drum (`kick`, `snare`, `hat`, `openHat`, `crash`, `ride`, `tom`, …) or a key number |

### Note

| Field | Type | Default | Meaning |
|---|---|---|---|
| `pitch` | `"D4"`, `"F#3"`, `"Bb2"`, a MIDI number, or a list of those (a chord) | required | C4 = MIDI 60 |
| `at` | time | required | Start |
| `dur` | length | required | How long it is held (the release rings after it) |
| `vel` | 0 … 1 | 0.8 | Velocity |
| `pan` | −1 … 1 | 0 | Within the track |

### Hit

| Field | Type | Default |
|---|---|---|
| `drum` | name or GM key | required |
| `at` | time | required |
| `vel` | 0 … 1 | 0.85 |
| `pan` | −1 … 1 | 0 |
| `tune` | 0.25 … 4 (pitch ratio; `synth` kit only) | 1 |
| `decay` | 0.1 … 4 (factor of the hit's length) | 1 |

### Clip (recorded audio)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `media` | path | required | The file; the engine decodes it |
| `in` | seconds ≥ 0 | 0 | In-point inside the file |
| `length` | length | to the file's end | How much of the file plays |
| `at` | time | required | Where it starts in the mix |
| `volume` | 0 … 4 | 1 | Clip gain |
| `pitch` | −24 … 24 semitones | 0 | Played like tape (pitch changes speed and length) |
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
| `tape` | `wow`, `flutter`, `age` (0.2 each, *env*) |
| `limiter` | `ceiling` (−1 dB), `release` (0.1 s) |
| `width` | `width` (1; 0 mono, 2 wider, *env*), `monoBelow` (120 Hz) |
| `gate` | `threshold` (−45 dB), `ratio` (4), `range` (30 dB), `attack` (0.002 s), `hold` (0.05 s), `release` (0.12 s) |
| `deess` | `freq` (6000 Hz), `threshold` (−30 dB), `range` (8 dB) |
| `dehum` | `freq` (0 = found in the clip; else 50 / 60), `harmonics` (6), `width` (40) |

### Ducks

`{"under": ["voice"], "depth": 0.5, "attack": 0.02, "release": 0.3, "lookahead": 0.01, "hold": 0.0, "voice": false}`: the track dips by up to `depth` (0 … 1 of its gain) while the named tracks sound. `voice: true` keeps the bass and lets the music swell back (for dialogue).

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
| `safetyClip` | true | The last soft clip above −1 dBFS |

## 3. Requests

Two ways in, the same requests and answers:

- **Long-lived process (the app's way):** `rostrum-sound serve`. One JSON request per line on stdin, one JSON answer per line on stdout, matched by `id`. Instruments, samples and decoded media stay loaded between requests, and each track's render is cached by its content, so a re-render after a small edit only renders the tracks that changed. `{"do": "quit"}` ends it.
- **One shot:** `rostrum-sound request <request.json>` answers one request and exits; `rostrum-sound render <schedule.json> <out.wav>` is short for a render request.
- Engine work only: `rostrum-sound render-job <job.json> <out.wav>` renders the internal job (`engine/src/mix/schedule/`) the contract compiles to. `play` (the live transport) still takes the internal job; it moves to the contract with the Sound screen.

Every answer is `{"id": …, "ok": true, "result": {…}}` or `{"id": …, "ok": false, "error": {…}}`. A failed render writes nothing under its output name (it renders to `<name>.partial` first).

| `do` | Fields | Answer |
|---|---|---|
| `describe` | — | `contract`, `engine` (version), and every accepted name: `tones`, `spaces`, `eqShapes`, `effects` (each with its fields and defaults), `builtIns`, `synthDrums`, `gmDrums`, `mediaFormats` |
| `check` | `schedule` | The schedule with every default filled in and every time in seconds (`resolved`), plus `length` and `tracks` count. Nothing is rendered |
| `render` | `schedule`, `out` (WAV path), optional `stems` (`"all"` or a list of track ids), `stemsDir` (default: beside `out`, named `<out stem>.stems`), `master` (true; false skips mastering) | `file`, `seconds`, `renderSeconds`, `lufs`, `truePeak`, `peak`, `lra`, `clipped`, `bands`, `series` (short-term loudness, true peak and stereo correlation every 100 ms), `tracks` (per track: `id`, `peak`, `rms`, `lufs`, `span`, `onsets`, `bands`), `stems` (`{id: path}`), `ducks` (where each duck dipped) |
| `range` | `instrument` (as in a track) | `low`, `high` (note names), `lowKey`, `highKey` (MIDI), `gaps` (keys inside the range with no sample), `layers` (velocity layers), `drums` (names a kit answers to) |

Files: the mix and the stems are 32-bit float WAV at `sampleRate`, stereo. A stem is its track as it reaches the master (after its effects, fader and ducks, before master effects and mastering), so the stems add up to the mix before the master bus. Meters are measured on the same signal.

## 4. How far this version goes (2026-10-21)

- Done: everything above.
- Not in version 1 yet (the engine can do them; a later version adds them to the contract): buses and sends, surround beds and objects, clip speed with pitch kept, time warps, glitch, filter sweeps, reverse, spectral repair, tone match, CLAP / VST3 plugins, note expression (glides, vibrato), the procedural instruments (`model.*`), speech.
- Not done: progress lines during a long render, and rendering only the changed part of a track (today the smallest unit that re-renders is a whole track).
