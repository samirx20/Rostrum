# Proof P-SND — sound against the reference

**Question.** Can sampled instruments, ACE-Step 1.5 and recorded effects, arranged and mixed by an agent through
Python, reach the level of the reference sound (the Arcane score; the sound design of Jibaro / The Witness)?
And what does an agent need in order to "hear"?

**Verdict so far: pass with conditions** (Sam listens to decide the quality bar; see the end).

## Results (for Sam to listen to)

All in `C:\Users\Sam\.rostrum\waves\results\stage1\p-snd\`:

| File | What it is |
|---|---|
| `cue-60s-sampled-orchestra.wav` | The 60-second cue: D minor, 96 bpm, strings / brass / timpani / drums / piano + recorded hits, composed and mixed by the agent through the Python driver |
| `cue-60s-first-mix.wav` | The same cue before the agent fixed the mix from its readings (for comparison) |
| `cue-60s-spectrogram.png`, `cue-60s-loudness-and-bands.png`, `cue-60s-first-mix-loudness-and-bands.png` | What the agent "saw" of the cue, after and before |
| `effects-20s-door.wav` | The 20-second effects pass, recorded CC0 effects only |
| `effects-20s-door-with-picture.mp4` | The same, muxed onto the clip (Mixkit clip, private, not in the repo) |
| `effects-20s-spectrogram-with-events.png` | Its spectrogram with the on-screen events marked |
| `acestep-bed-30s.wav`, `acestep-bed-30s-vs-cue.png`, `acestep-bed-layered-with-cue.wav` | ACE-Step 1.5's 30-second bed, the comparison picture, and the bed layered under the cue (see section ACE-Step) |

## Setup

- Python: the worktree's `.venv` (made with `uv venv`), packages `numpy scipy soundfile librosa pyloudnorm matplotlib`
  (`uv pip install --python .venv\Scripts\python.exe ...`).
- Engine: the archive's built `C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\native\target\release\rostrum-sound.exe`
  (not rebuilt; `RSND_ENGINE` points elsewhere).
- Instruments and effects: the experiment's asset library, installed at `C:\Users\Sam\.rostrum\assets\sounds\`.
  Licences in `LIBRARIES.md` (all 19 instrument packs and all 7 effects packs are shippable; four need a credit line).
- Run (from `proofs\sound`):
  - cue: `..\..\.venv\Scripts\python.exe cue\cue.py <out.wav> [--stems <dir>]`
  - effects: `..\..\.venv\Scripts\python.exe sfx\door_pass.py <out.wav> [--stems <dir>]`
  - listening: `..\..\.venv\Scripts\python.exe -m listen report <wav> --dir <dir>` (and `levels`, `onsets --expect`, `compare` …; see `listen\README.md`)
  - ACE-Step: see `acestep\gen_bed.py` (its own venv, through `heavy.ps1 … gpu`).

## How the Python driver talks to the engine (informs the Sound app's design)

`rsnd` (`rsnd\NOTES.md` has the detail):
- The agent writes music as Python calls: `s.track("horns", sfz=...)`, `.note("D4", at=, dur=, vel=)`, `.chord`,
  `.drum`, `.sample(path, at=, offset=, length=)`, `.effect(effects.eq(...))`, `.volume_automation`, `s.master(lufs=-16)`.
  Recorded effects by name through `Library().take("impact.metal-light", n)`.
- `Session.render(out.wav)` writes one JSON schedule (the engine's existing job format, version 9), runs
  `rostrum-sound.exe render <schedule> <out.wav>` once, and reads back the stats JSON (LUFS, true peak, per-track
  loudness and onsets). `render_stems(dir)` renders each track alone.
- Speed: a 60-second, 15-track orchestral cue renders in **2–3.5 s**; a 20-second, 5-track effects pass in under 1 s.
- **The engine fails loudly and usefully**: a note outside an instrument's range stops the render with
  `ViolaEnsSpic.sfz: no sample for A#2 (key 46) … the instrument plays C3–D6`. That message is exactly what the agent
  needs to fix the voicing; it hit three of these while writing the cue.
- What the Sound app should change (from building the driver): a documented, versioned schedule schema that rejects
  unknown names (today an unknown tone or EQ shape is silently replaced); defaults filled by the engine (a clip needs
  ~17 fields now); times in seconds / beats, not sample indices; the engine decoding media itself (path + in-point);
  a long-lived engine process that keeps instruments loaded and renders edits incrementally; stems and per-track
  meters as one request; and an "instrument range" query so an agent can voice before it renders.

## What the agent needed to "hear" (and what helped)

The agent cannot listen. It worked from `listen` (librosa ISC, pyloudnorm MIT, matplotlib) plus the engine's stats:

| Tool | What it caught in this proof | Did it help? |
|---|---|---|
| Short-term loudness curve (1 s steps) + band energy over time (`report` → `curves.png`) | Cue v1: the level **sagged** at 10–17 s (drone ended before the ostinato built) and **dipped** at 33 s in the middle of the build. Fixed by carrying the cellos to bar 8 and keeping the violin ostinato through the build: v2 climbs steadily from 5 s to the hit. | **Most useful** for musical shape (build / hit / release) |
| Per-stem levels (`levels` on `render_stems`) | Horns 9 dB over the strings; piano 12 dB under everything; timpani lost in the verse; in the effects pass, cloth **buried 22 dB** under the rest | **Very useful** — the mix balance came from this |
| Spectrogram with marks (`spectrogram --marks`) | Effects pass: a steady 50–150 Hz hum line through the whole room-tone recording → high-pass at 140 Hz. Cue: the hit at 42.5 s and the dark top end | Useful for faults you can *see* (hum, tones, masking) |
| Onsets vs expected times (`onsets --expect`) | Effects: 8 of 10 events at 0 ms; the brushed ring +44 ms and the palm swipe +31 ms late (soft-starting takes) → moved earlier by the measured amount. Cue: the hit lands 7 ms after 42.5 s | **Essential** for sync to picture |
| Stereo balance per section (`stereo`) | Cue intro leaned 6–8 dB to the right: piano samples carry a treble-right image and the engine's pan law is steep (pan 0.25 ≈ 6 dB) → re-panned; a 3–4 dB right lean is left in the first 10 s from the piano samples' own image | Useful; found a fact about the engine (pan law) |
| Integrated LUFS / true peak / LRA | Final cue −16.2 LUFS, −1.3 dBTP, LRA 11.7 LU; effects −20.2 LUFS, −1.3 dBTP, LRA 6.5 LU | Needed for delivery; says nothing about quality |

What the agent still **cannot** tell from these: whether the strings sound *real* or *sampled*, whether the brass
phrasing is musical, whether a take "sounds like" a padlock rather than a tin can, and taste in general. That stays
Sam's ear (and the reason for the side-by-side). A tool worth adding next: a per-note "what did this note actually
sound like" readout (attack time, pitch, brightness) so the agent can catch a wrong articulation without ears.

## Numbers

| | Value |
|---|---|
| Cue render (60 s, 15 tracks, 48 kHz) | 2.0–3.6 s wall, engine ~2.5 s |
| Cue loudness | −16.2 LUFS integrated, −1.3 dBTP, LRA 11.7 LU |
| Effects render (20.4 s, 5 tracks) | < 1 s |
| Effects sync | 10 events: 8 at 0 ms, 2 within 30–36 ms (one video frame = 40 ms) |
| Memory | engine and Python both under 1 GB; no GPU |

## ACE-Step 1.5

**It runs on this laptop's RTX 3050 (4 GB).**
- Licence: code MIT; weights tagged MIT on Hugging Face (no LICENSE file in the weights repo, worth a written
  confirmation before shipping). Training data, per the model card: licensed, royalty-free / public-domain and
  synthetic MIDI-rendered music. No GPL among its direct dependencies (`nano-vllm` and the indirect ones not audited).
- Setup: `git clone https://github.com/ACE-Step/ACE-Step-1.5` + `uv sync --python 3.12` (torch 2.7.1+cu128) in
  `C:\Users\Sam\.rostrum\waves\scratch\priyam-p1\acestep\repo\` (venv ~6.5 GB); weights without the LM planner:
  turbo DiT 4.5 GB + VAE 0.3 GB + Qwen3-Embedding-0.6B text encoder 1.2 GB = **6 GB** (31 min download).
- Settings for 4 GB (the project's own "tier 1"): DiT only (no LM planner), INT8 weights (`int8_weight_only`),
  everything offloaded to the CPU between uses, tiled VAE decode, 8 turbo steps. `acestep\gen_bed.py` (stops the
  library from fetching the 3.8 GB LM it doesn't use).
- **Numbers (one 30-second bed):** peak GPU memory **3.08 GB** allocated (3.35 GB on the card including the desktop),
  load 15.8 s, generate 22.8 s (diffusion itself 2.5 s; moving weights to and from the CPU 12 s), **77 s** wall for
  the whole job. Released right after (one process, ended).
- **Prompt:** dark cinematic hybrid orchestral, low strings ostinato, brass swells, taiko / timpani pulse, synth bass,
  building; asked for 96 bpm, D minor.

**How it compares to the sampled cue** (`acestep-bed-30s-vs-cue.png`, measured with `listen compare` and chroma):
- Tempo: **kept** — its sections change exactly every 2.5 s (96 bpm bars); a beat tracker near 96 reads 95.7.
  (The default beat tracker said 126; the spectrogram's bar grid was the reliable reading.)
- Key: **not kept** — it came out in A minor (A, F, E, C strongest; G# leading tone), not D minor. Without the LM
  planner the key request seems weak.
- Sound: 10–13 dB less energy above 2 kHz and 18 dB less sub than the cue — it sounds darker and more muffled;
  the parts start and stop in hard 2.5-second blocks, and the last 2 s are silent. It has more "mass" in the
  60–500 Hz range (low and low-mid +1.5 dB) and reads as one smeared texture rather than separate instruments.
- Control: the agent can't change one note, one instrument or one level inside it — only regenerate.

**Layering:** `cue\layer_bed.py` puts the bed under the cue's build (12.5–40 s), shifted **+5 semitones with the
engine's tempo-keeping pitch shift** (A minor → D minor), high-passed at 180 Hz so it doesn't fight the low strings,
−7 dB. After the shift the layered section's strongest notes are D, A, Bb (D minor) and bars line up. Result:
`acestep-bed-layered-with-cue.wav`. So: **it can be layered** as a texture / pad under sampled parts if the agent
measures its key and tempo and corrects them; it can't replace the composed parts.

## Libraries and licences

See `LIBRARIES.md` (sources, licences, sizes, gaps and gap-fill candidates) and the rows in `ATTRIBUTIONS.md`.
Gaps for a modern score: orchestral percussion beyond timpani (bass drum, cymbals, gong are in the full VSCO 2 / VCSL
repos, CC0, ~150–250 MB), big low brass (Karoryfer War Tuba, CC0), synth pads (FreePats, CC0), real choir (none clean
found), taiko (none clean found). The cue used recorded hits (braam, sub drop, riser) to stand in for the hybrid layer.

## Verdict so far — pass with conditions (Sam's ears decide the quality bar)

- **Python drives the Rust engine well.** One JSON schedule per render, results in seconds, loud and precise
  errors. Python is a good script layer for Sound. The schedule format needs to become a designed, documented
  interface (list under "How the Python driver talks to the engine").
- **Sampled cue:** the shape, balance and loudness are where the agent can measure them (steady build, the hit on
  time, −16 LUFS, brass and strings within 3 dB). Whether it reaches the Arcane score is for Sam to hear. The agent's
  own expectation: the arrangement is competent but plain next to Arcane — the libraries lack big percussion
  (only timpani), real choir and synth layers, and this cue used fixed velocities per note (the engine's SFZ `legato` / `swell`
  options and note expression were not tried). Those are the conditions: fill the library gaps (CC0 candidates in
  `LIBRARIES.md`) and try the expression options before judging the ceiling.
- **Effects pass:** recorded CC0 takes, layered and timed to within one frame, with low-end weight only on the big
  moments. The CC0 libraries are thin on close, detailed foley (no padlock, no iron ring, generic cloth); that limits
  the Jibaro / The Witness level more than the tools do. A licensed or self-recorded foley set is the condition.
- **ACE-Step 1.5:** fits 4 GB (3.1 GB peak, 77 s for 30 s). Usable as a bed / texture under composed parts after the
  agent corrects key (it ignored D minor); not a replacement for the composed, editable cue.
- **Hearing:** the agent needs the loudness curve, per-stem levels, onsets against expected times, a marked
  spectrogram and a stereo check — all built in `listen`. It can't judge realism or musicality; that remains Sam's.
