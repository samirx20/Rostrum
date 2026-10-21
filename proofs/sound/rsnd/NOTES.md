# rsnd — how Python drives the sound engine (proof P-SND)

## How it talks to the engine
- Python builds the whole mix as one JSON "schedule" (tracks → clips → notes, drum hits, recorded samples, effects, master settings).
- `Session.render(out.wav)` writes it to `out.schedule.json` beside the WAV, starts one engine process
  (`rostrum-sound.exe render <schedule> <out.wav>`), waits, and reads the stats JSON the engine prints
  (loudness, true peak, per-track peak / RMS / loudness / onsets / span, meter series).
- One process per render. A 10-second, 5-track mix takes about 0.3 s inside the engine, ~1.9 s with Python start-up.
- Any failure raises `RenderError` with the engine's own message (e.g. a missing SFZ file). Bad note names,
  unknown tones, reverb spaces, EQ shapes, instruments and drum names fail in Python before the engine runs.
- Recorded files (OGG / WAV / FLAC) are decoded once to raw stereo f32 at the mix's rate (soundfile + scipy
  resampling), cached by path + size + modified time + rate.

## What the schedule covers (and what rsnd exposes)
- Tracks: name, tone (neutral, warm, bright, muffled, sub-boost, voice-clarity, radio), volume, pan, reverb send,
  volume / pan automation, insert effects.
- Instruments: any SFZ file (VSCO 2 strings/brass/woodwinds, Salamander piano, …), the 10 built-in instruments,
  the engine's synthesized drum kit, or an SFZ drum kit on General MIDI keys (Muldjord `rostrum-gm.sfz`).
- Effects: EQ, compressor, reverb, delay, saturate, tape, limiter, stereo width, gate (all in `effects.py`).
- Master: loudness target (LUFS), true-peak ceiling, glue; master reverb and master inserts.
- Not exposed yet (the engine has them): ducking / sidechain, buses and sends, clip speed / pitch-keeping stretch,
  glitch, filter sweeps, reverse, synth and SoundFont specs, plugins, surround, note expression (glides, vibrato).

## What was awkward
- The format is the old TypeScript app's internal job, not a designed interface. Every clip needs ~17 fields
  (most `null` / `[]`), and the engine silently plays an unknown tone as "neutral" or an unknown EQ shape as
  "peak", so the driver must keep its own lists of valid names, copied from the Rust source.
- Times are sample counts (`startSample`, `startIdx` = the note's sample index inside its clip); Python converts.
- Clip buffer length (how long a note may ring) is the caller's guess; too short cuts tails silently.
- Recorded audio must be decoded and resampled by the caller and written as headerless f32 files.
- The only documentation of the format is Rust structs and TypeScript that built it.
- Per-track stats are measured before mastering, which is right for level checks but not stated anywhere.

## What the Sound app's design should change
1. **A stable, documented schedule schema** (JSON Schema, versioned) that rejects unknown names instead of
   guessing; defaults filled in by the engine, so a clip is a few fields, not seventeen.
2. **A long-lived engine process** (stdin/stdout or a local socket) that keeps instruments and decoded samples
   loaded, renders edits incrementally (its per-track cache already exists), and streams progress.
3. **Times in seconds or beats** in the schema, with one tempo map, not sample indices.
4. **The engine decodes media itself** (path + in-point), with its own content-keyed cache.
5. **Stems and per-track meters as first-class requests** ("render tracks A, B alone") instead of one render each.
