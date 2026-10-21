# Vendored crates: what we patched

The sound engine patches one crate from crates.io, copied here unchanged except where marked `Rostrum patch` in the source. `native/Cargo.toml` points `[patch.crates-io]` at it. rustysynth is MIT (`rustysynth/LICENSE.txt`); its terms apply to this copy. The patch is a candidate to send upstream.

| Crate (version) | Patch | Why |
|---|---|---|
| rustysynth 1.3.7 | **SoundFont modulators** (`modulator.rs`): the `pmod` / `imod` chunks are read (upstream discarded them); each region keeps its note-only modulators (sources fixed at note-on: velocity, key, none), instrument ones over the SF2 default modulators (velocity → attenuation, velocity → filter cutoff), preset ones added (SF2 2.04 §8, §9.5). `RegionPair::new` sums them for the note into the generators. The hard-coded velocity curve in `Voice::start` is now the default velocity → attenuation modulator (the same 40·log10 curve), so a font can replace it; the 0.4 factor stays on the attenuation generator only, as FluidSynth does | MuseScore General's pianos (GM 0/1/3) disable the default velocity modulators and shape their layers with their own: a ~300 Hz base cutoff opened by key and velocity, a velocity → mod-envelope filter sweep, velocity → attenuation per layer. Without them the soft and medium layers played through a 300 Hz low-pass, so level was not monotonic in velocity (0.3 louder than 0.6) and jumped ~20 dB into the loud layer above ~0.85. Measured at C4 after the patch: −55 dB at velocity 20 rising smoothly to −25 dB at 127 |
| rustysynth 1.3.7 | `RegionPair::get_initial_filter_q` clamped to 0..960 cB | A velocity → Q modulator takes Q below 0 dB, where the biquad's peak correction (`resonance − k / (1 + 6(resonance − 1))`) divides by ~0 and the voice blows up (silence, GM 3 at velocity 51) |

Not covered (left to the channel as before): modulators driven by MIDI controllers, pressure or the pitch wheel (rustysynth handles volume, pan, expression, modulation and pitch bend itself). Test: `sampler::tests::gm_level_rises_with_velocity` (every melodic GM program, when the font is installed).

The crate's own two loader tests (`soundfont::tests`) need sample files upstream keeps outside the published package, so they fail in this copy as in the crates.io one; the engine's tests cover the patch.

## Signalsmith Stretch 1.3.1 (not a crate)

`signalsmith-stretch/`: `signalsmith-stretch.h` and the three `signalsmith-linear` headers it includes (`fft.h`, `linear.h`, `stft.h`), copied unchanged from upstream (MIT, Geraint Luff / Signalsmith Audio; `LICENSE.txt` in each). `rostrum_stretch.cpp` is ours: the C functions `src/stretch.rs` calls (planar buffers, a fixed seed). `build.rs` compiles it with the `cc` crate.
