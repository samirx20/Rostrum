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
- Sound: `render_mix` (job: mix + every stem + per-track meters), `look_loudness`, `look_levels`, `look_events`, `look_spectrum`, `look_stereo`, `look_low_end`, `look_beats` (tempo, beat grid, onsets against the audio's and the document's beats, with picture; P10), `look_pitch` (pitch of one line as notes, cents, vibrato, drift, checked against the written notes; P10), `look_clash` (stems fighting in the same band at the same time, with picture; P10), `inspect_harmony` (key, chords per bar, range / low-interval / crossing / spacing / out-of-key checks on the written notes; P10), `inspect_engine`, `inspect_instrument`, `inspect_library`, `look_video` (frames / contact sheet / motion), `inspect_cuts` (the cut pool), `render_voice`, `edit_sounds_from_motion` (instrument parts or library recordings placed on the picture's motion, only the ones chosen), `inspect_plugins` (installed plug-ins and their settings, P8), `render_cleanup` (job: makes the missing cleaned takes of the clips: dialogue kept, noise and reverb out, stems; P9), `look_cleanup` (before vs after: noise floor, speech level, reverb tail; stems: level, leakage, SDR; with pictures).
- Guides: `start-here`, `script` (the script API), `listening` (which look tool answers which question), `scoring-motion` (answering movement with instruments, sounds from motion), `voice`, `cleanup` (dialogue, noise, reverb and stems: [`CLEANUP.md`](CLEANUP.md)).
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
| numpy, soundfile, matplotlib (shipped); scipy, librosa, pyloudnorm (`listen-dev` extra, comparison checks only) | (venv) | BSD-3 / BSD-3 / PSF-style; BSD-3 / ISC / MIT | apps/sound/python | Python package | numpy, soundfile, matplotlib ship; scipy, librosa, pyloudnorm dev only (P22) | Keep the notices | https://pypi.org |
| annotated-types | 0.8.0 | MIT | MCP servers (through pydantic) | Python package | ships | Keep the notice | https://github.com/annotated-types/annotated-types |
| anyio | 4.15.1 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/agronholm/anyio |
| attrs | 26.1.0 | MIT | MCP servers (through jsonschema) | Python package | ships | Keep the notice | https://github.com/python-attrs/attrs |
| cffi | 2.1.1 | MIT-0 | soundfile, cryptography | Python package | ships | — | https://github.com/python-cffi/cffi |
| click | 8.5.0 | BSD-3-Clause | MCP servers (through uvicorn) | Python package | ships | Keep the notice | https://github.com/pallets/click |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause (bundles OpenSSL, Apache-2.0) | MCP servers (through PyJWT) | Python package | ships | Keep the notice | https://github.com/pyca/cryptography |
| h11 | 0.16.0 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/python-hyper/h11 |
| httpcore2 | 2.16.0 | BSD-3-Clause | MCP servers | Python package | ships | Keep the notice | https://github.com/pydantic/httpx2 |
| httpx2 | 2.16.0 | BSD-3-Clause | MCP servers | Python package | ships | Keep the notice | https://github.com/pydantic/httpx2 |
| idna | 3.20 | BSD-3-Clause | MCP servers | Python package | ships | Keep the notice | https://github.com/kjd/idna |
| jsonschema | 4.26.0 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/python-jsonschema/jsonschema |
| jsonschema-specifications | 2025.9.1 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/python-jsonschema/jsonschema-specifications |
| mcp | 2.3.0 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/modelcontextprotocol/python-sdk |
| mcp-types | 2.3.0 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/modelcontextprotocol/python-sdk |
| opentelemetry-api | 1.45.1 | Apache-2.0 | MCP servers | Python package | ships | Keep the notice | https://github.com/open-telemetry/opentelemetry-python |
| pycparser | 3.11 | BSD-3-Clause | cffi | Python package | ships | Keep the notice | https://github.com/eliben/pycparser |
| pydantic | 2.14.1 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/pydantic/pydantic |
| pydantic_core | 2.50.1 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/pydantic/pydantic-core |
| PyJWT | 2.15.1 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/jpadilla/pyjwt |
| python-multipart | 0.0.32 | Apache-2.0 | MCP servers | Python package | ships | Keep the notice | https://github.com/Kludex/python-multipart |
| pywin32 | 312 | PSF-2.0 | MCP servers (Windows) | Python package | ships | Keep the notice | https://github.com/mhammond/pywin32 |
| referencing | 0.37.0 | MIT | MCP servers (through jsonschema) | Python package | ships | Keep the notice | https://github.com/python-jsonschema/referencing |
| rpds-py | 2026.9.1 | MIT | MCP servers (through jsonschema) | Python package | ships | Keep the notice | https://github.com/crate-py/rpds |
| sse-starlette | 3.5.0 | BSD-3-Clause | MCP servers | Python package | ships | Keep the notice | https://github.com/sysid/sse-starlette |
| starlette | 1.9.0 | BSD-3-Clause | MCP servers | Python package | ships | Keep the notice | https://github.com/Kludex/starlette |
| truststore | 0.10.5 | MIT | MCP servers | Python package | ships | Keep the notice | https://github.com/sethmlarson/truststore |
| typing_extensions | 4.16.0 | PSF-2.0 | pydantic, MCP | Python package | ships | Keep the notice | https://github.com/python/typing_extensions |
| typing-inspection | 0.4.4 | MIT | pydantic | Python package | ships | Keep the notice | https://github.com/pydantic/typing-inspection |
| uvicorn | 0.54.0 | BSD-3-Clause | MCP servers | Python package | ships | Keep the notice | https://github.com/Kludex/uvicorn |
| matplotlib | 3.11.2 | PSF-based (matplotlib licence, BSD-compatible) | Sound: the listen pictures (Mix page and agent looks), loaded only to draw | Python package | ships (replaces the "dev only" row) | Keep the notice | https://matplotlib.org |
| contourpy | 1.4.0 | BSD-3-Clause | matplotlib | Python package | ships | Keep the notice | https://github.com/contourpy/contourpy |
| cycler | 0.12.1 | BSD-3-Clause | matplotlib | Python package | ships | Keep the notice | https://github.com/matplotlib/cycler |
| kiwisolver | 1.5.1 | BSD-3-Clause | matplotlib | Python package | ships | Keep the notice | https://github.com/nucleic/kiwi |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause | matplotlib | Python package | ships | Keep the notice | https://github.com/pypa/packaging |
| pyparsing | 3.3.3 | MIT | matplotlib | Python package | ships | Keep the notice | https://github.com/pyparsing/pyparsing |
| python-dateutil | 3.0.0 | Apache-2.0 AND BSD-3-Clause (dual) | matplotlib | Python package | ships | Keep the notice | https://github.com/dateutil/dateutil |
| six | 1.17.0 | MIT | python-dateutil | Python package | ships | Keep the notice | https://github.com/benjaminp/six |
| tzdata | 2026.5 | Apache-2.0 | python-dateutil (time zones) | Python package | ships | Keep the notice | https://github.com/python/tzdata |
| soundfile with libsndfile 1.2.2 (inside: LAME, mpg123, FLAC, Ogg/Vorbis/Opus) | 0.14.0 | BSD-3-Clause (soundfile); LGPL-2.1+ (libsndfile, LAME, mpg123; BSD for FLAC / Xiph) | Sound: reading audio, delivery files (WAV, FLAC, MP3 export) | dynamic (libsndfile_x64.dll, loaded through cffi) | ships (replaces the "dev only" part of the numpy / scipy / soundfile row) | Keep the DLL separate and replaceable; ship the LGPL notice; offer the source | https://github.com/bastibe/python-soundfile |
| opencv-python-headless (bundles FFmpeg, LGPL) | 5.0.0.93 | Apache-2.0 (OpenCV); LGPL-2.1+ (its FFmpeg DLL) | Sound: the video looks (`look_video`, motion), downloaded on first use by `python -m rostrum_sound.sfx.opencv` | dynamic (downloaded wheel, unpacked into the models folder) | downloaded on first use, not in the installer | Keep the notices; FFmpeg stays a separate DLL | https://github.com/opencv/opencv-python |
| Rostrum Sound engine crates | see `apps/sound/engine/DEPENDENCIES.md` | 173 crates: MIT / Apache-2.0 mostly; MPL-2.0 (Symphonia); Zlib, ISC, BSD, Unicode-3.0; no copyleft | `rostrum-sound.exe` | static (Rust) | ships | Keep the notices; MPL files unmodified | `apps/sound/engine/deps.py` (regenerate; `--check` refuses GPL) |
