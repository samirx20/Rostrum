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
| `buses` | list | `[]` | Buses tracks feed and send to (§ Buses and sends) |

### Track

| Field | Type | Default | Meaning |
|---|---|---|---|
| `id` | string `[A-Za-z0-9_.-]{1,64}` | required, unique | Names the track everywhere (meters, stems, errors, ducks) |
| `instrument` | object | none | What plays `notes` / `hits`; exactly one key, below. Required when the track has notes or hits |
| `notes` | list | `[]` | Pitched notes and chords |
| `hits` | list | `[]` | Drum hits |
| `clips` | list | `[]` | Recorded audio |
| `sounds` | list | `[]` | Designed sounds: whoosh, click, riser, hit, sub drop (§ Designed sounds) |
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

### Instrument (one key)

| Form | Meaning |
|---|---|
| `{"builtIn": "grandPiano"}` | A synthesized instrument: `feltPiano`, `grandPiano`, `warmPad`, `analogStrings`, `spiccatoStrings`, `choirPad`, `cinematicBrass`, `subBass`, `shepardRiser`, `glassMarimba` |
| `{"sfz": "<path>", "legato": false, "swell": false}` | A sampled instrument (SFZ file). A note outside its samples fails and names the range |
| `{"kit": "synth"}` | The engine's synthesized drum kit: `kick`, `snare`, `clap`, `hat`, `openHat`, `cymbal`, `tom`, `rim` |
| `{"kitSfz": "<path>"}` | An SFZ drum kit on General MIDI keys; hits name a GM drum (`kick`, `snare`, `hat`, `openHat`, `crash`, `ride`, `tom`, …) or a key number |
| `{"model": "guitar", "position": 0.13, "damping": 0, "hardness": 0.5}` | A procedural instrument (§ 2a): `guitar`, `nylonGuitar` (plucked strings), `marimba`, `vibraphone`, `glockenspiel`, `tubularBell` (struck bars), `violin` (a bowed solo voice, learned model). The touch fields are the track's defaults; a note may override them |
| `{"synth": "saw", "attack": 0.3, "brightness": 2400, …}` | A subtractive synth (§ 2a): the value is the wave (`saw`, `square`, `triangle`, `sine`) |
| `{"plugin": {"format": "clap", "path": "C:\\…\\Synth.clap", "id": "<id>", "params": {…}, "state": "<base64>"}}` | A CLAP / VST3 instrument plugin (§ Plugins). One instance plays all the track's notes (its own polyphony and releases) |

An `sfz` instrument may also name **articulations**: `{"sfz": "<sustain.sfz>", "articulations": {"spiccato": "<spic.sfz>", "tremolo": "<trem.sfz>"}}`. A note picks one with `"art": "spiccato"`; without `art` it plays the main file. This is the keyswitch for libraries that ship one file per playing style (VSCO 2, most CC0 libraries); SFZ files with `sw_*` keyswitch opcodes are still refused with that message.

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

### Track expression (CC-style lanes; added 2026-10-21, P4)

A track may carry `expression`: `{"dynamics": [[time, level 0 … 2], …], "vibrato": [[time, amount 0 … 1], …], "vibratoRate": 5.5, "vibratoDepth": 25}`. Times are times (seconds or beats). Like a MIDI player's CC 11 (expression) and CC 1 (mod wheel): the lanes run across notes, straight lines between points, held before the first and after the last. `dynamics` multiplies every note's level (with the note's own `dynamics`); `vibrato` is the mod wheel, 1 = `vibratoDepth` cents at `vibratoRate` Hz, 0 = none (a note's own `vibrato` adds to it). Works on every pitched instrument (sampled, built-in, synth, model).

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
| `tape` | `wow`, `flutter`, `age` (0.2 each, *env*) |
| `limiter` | `ceiling` (−1 dB), `release` (0.1 s) |
| `width` | `width` (1; 0 mono, 2 wider, *env*), `monoBelow` (120 Hz) |
| `gate` | `threshold` (−45 dB), `ratio` (4), `range` (30 dB), `attack` (0.002 s), `hold` (0.05 s), `release` (0.12 s) |
| `deess` | `freq` (6000 Hz), `threshold` (−30 dB), `range` (8 dB) |
| `dehum` | `freq` (0 = found in the clip; else 50 / 60), `harmonics` (6), `width` (40) |
| `dereverb` | `amount` (0.5: how much of the modelled late reverb is taken out), `reduction` (18 dB at most), `time` (0 = the room's decay time measured from the clip, else RT60 in s). Statistical late-reverb suppression, no model (`dialogue/dereverb.rs`); offline only (not on live play) |
| `plugin` | `format` (`clap` / `vst3`), `path`, `id`, `params` ({}), `state` (none): a CLAP / VST3 effect plugin (§ Plugins) |

Clip `stretch` and `shift` (added 2026-10-21, P8) use the engine's stretcher (Signalsmith Stretch for music, PSOLA when the engine hears a voice in the clip); both may be set together, and with `pitch`. `check` writes `null` for the ones not set.

### Designed sounds (added 2026-10-21, P6)

A track's `sounds`: `[{"design": "whoosh", "at": 1.0, "dur": 0.8, …}, …]`. Each is built from layers in the engine
(`engine/src/design/`), peak-normalized to its design's own level times `volume`, so a sound's level is a choice, never
an accident of its settings. The field table in `design/mod.rs` is the one source of truth; `describe` answers it under
`designs` (`common`, `designs`, `lanes`) and the Python side checks itself against it. Every field is optional except
`design`, `at` and a whoosh's or riser's `dur`.

| Design | Its own fields (default) | What it is |
|---|---|---|
| all | `volume` 0 … 4 (1), `pan` −1 … 1 (0), `width` 0 … 1 (0.5), `seed` 1 … 999999 (1) | `seed`: another take of the same design |
| `whoosh` | `dur` 0.04 … 10 (required), `brightness` (0.5), `size` (0.5), `doppler` (0.3), `tone` (0.25), `air` (0.4), `texture` (0.2); lanes `speed`, `panPath` | Band-passed noise body, low weight (size), high air at the fastest moment, a tuned whistle, flutter; the pitch falls past the fastest point |
| `click` | `pitch` 100 … 12000 Hz (1800), `material` (0.3: plastic 0, glass 0.5, metal 1), `tight` (0.6), `body` (0.6), `transient` (0.7), `air` (0.3), `bend` −1 … 1 (0) | Transient + tuned body (partials from the material) + knock + air; also tick, tap, pop (`bend` < 0) |
| `riser` | `dur` 0.1 … 20 (required), `pitch` 40 … 2000 (220), `brightness` (0.5), `curve` (0.5), `tone` (0.4), `air` (0.4), `texture` (0.5) | Noise sweep + detuned stack climbing two octaves to its end, accelerating flutter |
| `hit` | `pitch` 25 … 200 (50), `size` (0.6), `brightness` (0.5), `tail` 0.05 … 6 s (1.2), `drive` (0.3) | Sub thump falling into its pitch, mid body, crack, tail, saturated together |
| `subDrop` | `dur` 0.1 … 8 (1.2), `pitch` 25 … 200 (40), `drop` 0 … 4 octaves (1.5), `drive` (0.2) | A sine falling into its pitch |

Unmarked ranges are 0 … 1. A whoosh's **`speed`** is `[[fraction of dur, speed 0 … 1], …]` (fractions rising; default a
bell peaking at 0.55): level, the sweep's centre and the air follow it, so the sound has the move's own shape.
**`panPath`** `[[fraction, pan], …]` moves it with the object (it overrides `pan`). Both are refused on other designs.

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
| `safetyClip` | true | The last soft clip above −1 dBFS |

## 3. Requests

Two ways in, the same requests and answers:

- **Long-lived process (the app's way):** `rostrum-sound serve`. One JSON request per line on stdin, one JSON answer per line on stdout, matched by `id`. Instruments, samples and decoded media stay loaded between requests, and each track's render is cached by its content, so a re-render after a small edit only renders the tracks that changed. `{"do": "quit"}` ends it.
- **One shot:** `rostrum-sound request <request.json>` answers one request and exits; `rostrum-sound render <schedule.json> <out.wav>` is short for a render request.
- Engine work only: `rostrum-sound render-job <job.json> <out.wav>` renders the internal job (`engine/src/mix/schedule/`) the contract compiles to. `play` (the live transport) still takes the internal job; it moves to the contract with the Sound screen.

Every answer is `{"id": …, "ok": true, "result": {…}}` or `{"id": …, "ok": false, "error": {…}}`. A failed render writes nothing under its output name (it renders to `<name>.partial` first).

| `do` | Fields | Answer |
|---|---|---|
| `describe` | — | `contract`, `engine` (version), and every accepted name: `tones`, `spaces`, `eqShapes`, `effects` (each with its fields and defaults), `builtIns`, `synthDrums`, `gmDrums`, `mediaFormats`, `pluginFormats`. Installed plugins are not listed here (that loads each one): ask `plugins` |
| `check` | `schedule` | The schedule with every default filled in and every time in seconds (`resolved`), plus `length` and `tracks` count. Nothing is rendered |
| `render` | `schedule`, `out` (WAV path), optional `stems` (`"all"` or a list of track ids), `stemsDir` (default: beside `out`, named `<out stem>.stems`), `master` (true; false skips mastering) | `file`, `seconds`, `renderSeconds`, `lufs`, `truePeak`, `peak`, `lra`, `clipped`, `bands`, `series` (short-term loudness, true peak and stereo correlation every 100 ms), `tracks` (per track: `id`, `peak`, `rms`, `lufs`, `span`, `onsets`, `bands`), `stems` (`{id: path}`), `busStems` (`{bus id: path}`, when any stem is asked for and there are buses), `direct` (track ids), `ducks` (where each duck dipped) |
| `range` | `instrument` (as in a track) | `low`, `high` (note names), `lowKey`, `highKey` (MIDI), `gaps` (keys inside the range with no sample), `layers` (velocity layers), `drums` (names a kit answers to) |
| `plugins` | optional `path` (a `.clap` / `.vst3`, or a folder, searched 4 levels deep) | Without `path`: the standard folders (`CLAP_PATH`, `VST3_PATH`, `%LOCALAPPDATA%\Programs\Common\CLAP` and `…\VST3`, `C:\Program Files\Common Files\CLAP` and `…\VST3`) and `%USERPROFILE%\.rostrum\assets\plugins`. Answers `folders` (searched), `plugins` (each: `format`, `path`, `id`, `name`, `vendor`, `kind` (`effect` / `instrument`), `hasWindow`, `params`: `[{id, name, min, max, default, steps?, unit?, plainMin?, plainMax?}]`; `steps` only on stepped parameters; `plainMin` / `plainMax` the VST3 range the 0 … 1 value stands for) and `failed` (files that would not load, each with its `error`). Each plugin is loaded in the engine's own process to read it |
| `pluginWindow` | `plugin`: a plugin (§ Plugins; `params` and `state` optional) | Opens the plugin's own window for a person and answers when they close it: `state` (base64, for the document), `params` (`{id: value}`: the current values of the parameters the request named; everything else is in `state`), `errors` (anything the plugin reported meanwhile). Nothing else is answered while the window is open. The window runs in its own process (`rostrum-sound plugin`), so a plugin crash fails the request (`JOB_FAILED`), not the engine |

Files: the mix and the stems are 32-bit float WAV at `sampleRate`, stereo. A stem is its track as it reaches the master (after its effects, fader and ducks, before master effects and mastering), so the stems add up to the mix before the master bus. Meters are measured on the same signal.

## 4. How far this version goes (2026-10-21)

- Done: everything above.
- Not in version 1 yet (the engine can do them; a later version adds them to the contract): surround beds and objects, speed ramps and warp markers, formant control, time warps, glitch, filter sweeps, reverse, spectral repair, tone match, plugin presets and MIDI controller lanes to plugins, the procedural drum kit (`model.kit`), speech. (Note expression, articulations, the procedural instruments and the synth were added on 2026-10-21, P4; buses and sends on 2026-10-21, P5; clip `stretch` / `shift`, CLAP / VST3 effects and instruments and the `plugins` / `pluginWindow` requests on 2026-10-21, P8. Each addition only adds optional fields and requests, so the contract name stays `rostrum-sound-schedule/1`.)
- Not done: progress lines during a long render, and rendering only the changed part of a track (today the smallest unit that re-renders is a whole track).
