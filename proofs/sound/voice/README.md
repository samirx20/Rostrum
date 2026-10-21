# P5 Voice proof — a voice-over on markers, over the cue

**Question:** can the Sound app make a spoken line with the vetted voice model on this laptop, place it on a named marker, and mix it under / over the music the way a person or an agent would?

**Verdict: pass, Sam to listen.** Two lines of our own ("Every city keeps one hour for itself." on the marker `first-words`, "This is that hour. Listen." on `second-words` + 0.25 s) were made by Qwen3-TTS on the graphics card, cached, and mixed over the P4 expressive cue; the music dips about 6 dB under each line and swells back; the voice has a little room through a reverb bus. The captions model (Parakeet) hears every line exactly as written.

## Setup
- `voice_over.py` (this folder): the P4 cue script (`proofs/sound/cue/cue_expressive.py`), then operations only (`marker.add`, `track.add` with `instrument: voice`, `line.add`, `duck.add` on each music track with `voice: true`, `bus.add` + reverb, `send.add`), then `make_lines` (one model run per missing line), then one engine render. Run inside `heavy.ps1 … gpu`.
- Model: Qwen3-TTS 1.7B CustomVoice, talker Q6_K + codec Q8_0, run by qwentts.cpp (`C:\Users\Sam\.rostrum\models\qwentts\`, already installed from the experiment, 3.5 GB on disk). Voice "ryan", style "low and unhurried, close to the microphone, warm, a little tired", English.

## Results (all in `C:\Users\Sam\.rostrum\waves\results\stage2\sound-voice\`)
- `C:\Users\Sam\.rostrum\waves\results\stage2\sound-voice\voice-over-on-cue.wav` — the 60 s mix (listen at 0–20 s).
- `C:\Users\Sam\.rostrum\waves\results\stage2\sound-voice\voice-over-on-cue.stems\vo.wav` — the voice alone, as it reaches the mix.
- `C:\Users\Sam\.rostrum\waves\results\stage2\sound-voice\voice-over-schedule.json` — what the engine was given.
- `C:\Users\Sam\.rostrum\waves\results\stage2\sound-voice\project\` — the saved document (open it: `main.py --doc <that folder> voice-over`).
- Screens: `C:\Users\Sam\.rostrum\waves\results\stage2\sound-screen\p5-voice-card.png`, `p5-timeline-voice-lines.png`, `p5-mix-voice-over.png`.

## Numbers
| | |
|---|---|
| Line 1 (5.3 s of speech) | made in 7.4 s |
| Line 2 (3.3 s) | made in 4.1 s |
| An earlier test line (5.9 s) | 11.6 s, cold start |
| Graphics card memory | peak 3.0 GB used (sampled every 0.5 s; 0.1 GB before) of 4 GB |
| Free memory gate | 2.5 GB free RAM before a line starts (from the experiment's measurement) |
| Re-render with every take cached | no model run (the cache answers) |
| Mix | −16.1 LUFS, true peak −1.3 dBTP; voice −21.3 LUFS; the room bus −36.9 LUFS |
| Ducking | every music track dips −6 dB from 3.17–7.86 s and 12.87–16.65 s (the lines + hold + release) |
| Captions check (Parakeet 0.6B v3) | "Every city keeps one hour for itself." / "This is that hour. Listen." / "Somewhere past the last street light, the city finally goes quiet." — all as written |

## For Sam's ear
- Line 1's take has a short soft sound (breath-like) about 0.8 s after its last word; the captions model hears no word there. If it bothers you, a new take is one click (another take number).
- How the ducking feels against the strings and the piano motif.

## Attribution rows
| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| Qwen3-TTS 1.7B CustomVoice + tokenizer (weights, Q6_K / Q8_0 GGUF) | 12Hz, GGUFs from Serveurperso/Qwen3-TTS-GGUF b7ee2e8 | Apache-2.0 | `apps/sound/python/rostrum_sound/voice.py` | model | yes (downloaded on demand) | Keep the licence and notice | https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice |
| qwentts.cpp (with GGML) | 01b6127 | MIT | `apps/sound/python/rostrum_sound/voice.py` | separate program | yes (downloaded on demand) | Keep the licence (`LICENSE-qwentts.txt`) | https://github.com/ServeurpersoCom/qwentts.cpp |
| sherpa-onnx (+ sherpa-onnx-core) | 1.13.8 | Apache-2.0 | captions check in this proof | Python package | dev only | Keep the notice | https://github.com/k2-fsa/sherpa-onnx |
