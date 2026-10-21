# RostrumSound

Music, sound effects, voice, recording and mixing. The one audio engine: every sound in every app renders through it.

| Part | Where | What |
|---|---|---|
| Engine (Rust) | `engine/` | The experiment's sound engine, moved in (P3, 2026-10-21): sampled and synthesized instruments, effects, mastering, analysis, live play and recording, CLAP / VST3 hosting. The way in is the contract |
| Engine contract | [`ENGINE_CONTRACT.md`](ENGINE_CONTRACT.md), `engine/src/contract/` | `rostrum-sound-schedule/1`: versioned, strict (unknown names fail with where and "did you mean"), defaults filled by the engine, seconds / beats, media decoded by the engine, mix + stems + meters in one request, instrument range, a long-lived `serve` process |
| Python layer | `python/rostrum_sound/` | The Sound document on `rostrum_core` (items, 23 operations with `valid_when` / `importance`), its script layer, the compiler to the contract, the engine client |
| Listening and effects helpers | `python/rostrum_sound/listen/`, `sfx/` | Loudness, stem levels, onsets vs expected, marked spectrogram with hum lines, stereo, low end; eyes on the picture, the cut pool (cached), level from force, the event sheet |
| MCP server `rostrum-sound` | `python/rostrum_sound/mcp/` | 22 tools on `rostrum_core.mcp` (below) |
| Screen | `screen/` | Instruments → Timeline → Mix on `shared/gui-kit/` (P4): cards built from `valid_when` / `importance`, arrangement + piano roll + markers + engine playback, mixer with effect chains, meters, loudness and listen pictures ([`screen/README.md`](screen/README.md)) |

Hands over WAV stems (see `shared/HANDOFFS.md`).

## Build and run

```
cd apps\sound\engine
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "<team>: sound engine" build cargo build --profile agent -j 4
uv pip install --python <worktree>\.venv\Scripts\python.exe -e "shared\core[mcp]" -e "apps\sound\python[listen,mcp,cleanup,test]"
<worktree>\.venv\Scripts\python.exe -m rostrum_sound.mcp.server --folder <project folder> --item cue
```

The engine is found at `engine\target\release\` or `engine\target\agent\`, or `ROSTRUM_SOUND_ENGINE`. A first build takes ~3 min; after a change ~45 s.

Tests (minimal): `cargo test --profile agent -j 4 contract::` (unknown names refused, defaults and beats, the render round trip with stems and decoded media) and `python -m pytest apps\sound\python\tests` (a script re-run keeps a person's level edit; compile and markers; onsets vs expected; the cut pool's cache).

## MCP tools

- Shared (`rostrum_core`): `inspect_project`, `inspect_item`, `inspect_markers`, `inspect_history`, `inspect_operations`, `inspect_guide`, `inspect_job`, `edit_document`, `run_script`, `run_stop`.
- Sound: `render_mix` (job: mix + every stem + per-track meters), `look_loudness`, `look_levels`, `look_events`, `look_spectrum`, `look_stereo`, `look_low_end`, `inspect_engine`, `inspect_instrument`, `inspect_library`, `look_video` (frames / contact sheet / motion), `inspect_cuts` (the cut pool), `render_voice`, `edit_sounds_from_motion` (designed sounds placed from the picture's motion, P6), `inspect_plugins` (installed plug-ins and their settings, P8), `render_cleanup` (job: makes the missing cleaned takes of the clips: dialogue kept, noise and reverb out, stems; P9), `look_cleanup` (before vs after: noise floor, speech level, reverb tail; stems: level, leakage, SDR; with pictures).
- Guides: `start-here`, `script` (the script API), `listening` (which look tool answers which question), `designed-sounds` (motion-design effects: the designs, their controls, sounds from motion), `voice`, `cleanup` (dialogue, noise, reverb and stems: [`CLEANUP.md`](CLEANUP.md)).
- `python/devtools/mcp_session.py` runs a list of tool calls over stdio as a plain MCP client; `python/devtools/person_edit.py` stands in for the Sound screen (an edit recorded as a person's) until the screen exists.

## Plug-ins (CLAP / VST3)

A track can be played by a plug-in and any insert chain can hold one (Mix page: "+" › "Add plug-in…"; Instruments page: "Choose plug-in…"; MCP: `inspect_plugins`, then `effect.add` / `track.set`). The document keeps one `plugin` record (`doc/plugins.py`). **Licence:** a user may load any plug-in they own, GPL ones such as Surge XT included, but we never bundle one: this repo and the installer ship no plug-ins.

## How far the engine contract got (P3)

- Done: every item in P1's list. Versioned and documented; unknown names refused loudly (an unknown field, effect, tone, space, EQ shape, instrument, drum or note name); defaults filled in the engine (a note is `pitch`, `at`, `dur`); seconds or beats through a tempo map; the engine decodes media itself (WAV, FLAC, OGG, MP3, MP4 / MOV audio) into a content-keyed cache; one render request returns the mix, stems and every track's meters; `range` answers what an instrument plays; `describe` lists every accepted name, which the Python side checks itself against.
- **The long-lived process works:** `rostrum-sound serve` keeps instruments, samples and decoded media loaded between requests; each track's render is cached by its content, so after a small edit only the changed tracks render. The MCP server keeps one engine process per session.
- Not yet: progress lines during a long render; re-rendering only the changed part of a track; buses, surround, plugins, stretch and the other engine features the contract does not expose yet (ENGINE_CONTRACT.md § 4); `play` (the live transport) still takes the internal job.

## Attribution rows

The engine's direct dependencies (228 crates in all, checked with `cargo metadata`: all MIT / Apache-2.0 / BSD / ISC / Zlib / Unlicense / CC0 / MPL-2.0; no GPL; one crate offers LGPL only as a third choice next to MIT and Apache-2.0).

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| Firewheel (+ cpal 0.18, Apache-2.0) | 0.14.0 | MIT OR Apache-2.0 | apps/sound/engine (audio output) | static | yes | Keep the notice | https://github.com/BillyDM/firewheel |
| rustysynth (vendored, patched) | 1.3.7 | MIT | apps/sound/engine (SoundFont player) | vendored source | yes | Keep `vendor/rustysynth/LICENSE.txt` | https://github.com/sinshu/rustysynth |
| Signalsmith Stretch + Signalsmith Linear (vendored) | 1.3.1 | MIT | apps/sound/engine (time stretch) | vendored source | yes | Keep the two LICENSE.txt files | https://github.com/Signalsmith-Audio/signalsmith-stretch |
| clack-host, clack-extensions | 0.2.0 | MIT OR Apache-2.0 | apps/sound/engine (CLAP hosting) | static | yes | Keep the notice | https://github.com/prokopyl/clack |
| vst3 (bindings) | 0.3.0 | MIT OR Apache-2.0 | apps/sound/engine (VST3 hosting) | static | yes | Keep the notice | https://github.com/coupler-rs/vst3-rs |
| symphonia (wav, pcm, flac, ogg, vorbis, mp3, isomp4, aac) | 0.5.5 | MPL-2.0 | apps/sound/engine (media decoding, contract/media.rs) | static (unmodified) | yes | Keep the notice; changes to its files would have to be published (we change none) | https://github.com/pdeljanov/Symphonia |
| rubato | 5.0.1 | MIT OR Apache-2.0 | apps/sound/engine (resampling) | static | yes | Keep the notice | https://github.com/HEnquist/rubato |
| rustfft, realfft | 6.4.1, 3.5.0 | MIT OR Apache-2.0, MIT | apps/sound/engine (analysis, convolution) | static | yes | Keep the notice | https://github.com/ejmahler/RustFFT |
| ebur128 | 0.1.10 | MIT | apps/sound/engine (loudness) | static | yes | Keep the notice | https://github.com/sdroege/ebur128 |
| freeverb | 0.2.0 | MIT | apps/sound/engine (reverb) | static | yes | Keep the notice | https://crates.io/crates/freeverb |
| claxon | 0.4.3 | Apache-2.0 | apps/sound/engine (FLAC samples) | static | yes | Keep the notice | https://github.com/ruuda/claxon |
| png | 0.18.1 | MIT OR Apache-2.0 | apps/sound/engine (spectrogram) | static | yes | Keep the notice | https://github.com/image-rs/image-png |
| blake3 | 1.8.7 | CC0-1.0 OR Apache-2.0 | apps/sound/engine (cache keys) | static | yes | None (CC0) | https://github.com/BLAKE3-team/BLAKE3 |
| audioadapter-buffers | 5.2.0 | MIT OR Apache-2.0 | apps/sound/engine | static | yes | Keep the notice | https://crates.io/crates/audioadapter-buffers |
| windows | 0.62.2 | MIT OR Apache-2.0 | apps/sound/engine (WASAPI, plugin windows) | static | yes | Keep the notice | https://github.com/microsoft/windows-rs |
| serde, serde_json, cc | 1.x, 1.7.0 | MIT OR Apache-2.0 | apps/sound/engine | static / build tool | yes / build only | Keep the notice | https://serde.rs |
| SADIE II HRIR, subject D2 (data) | Zenodo 12092466 | Apache-2.0 | apps/sound/engine (binaural fold) | data | yes | Keep `data/SADIE-II-NOTICE.txt` (changes listed there) | https://www.york.ac.uk/sadie-project/database.html |
| DDSP violin weights (data) | ours, 2026-10-15 | MIT (ours; trained on VSCO 2 CE, CC0) | apps/sound/engine (`ddsp.violin`) | data | yes | None | experiment-final:docs/AI_MODELS.md |
| opencv-python-headless | 5.0.0.93 | Apache-2.0 | apps/sound/python (sfx eyes) | Python package | yes | Keep the notice | https://opencv.org |
| numpy, scipy, soundfile, librosa, pyloudnorm, matplotlib | (venv) | BSD-3 / BSD-3 / BSD-3 / ISC / MIT / PSF-style (matplotlib) | apps/sound/python (listen, sfx) | Python package | yes | Keep the notices (libsndfile under soundfile is LGPL-2.1, dynamically loaded) | https://pypi.org |
