# Proof: Sound cleanup tools (P9, Package A)

**Question.** Can RostrumSound clean a recording (noise, room, dialogue out of music) and split music into stems
with vetted models only (code and weights allowed for commercial use), computed once and stored, on this laptop?

**Setup.** `apps/sound/python/rostrum_sound/cleanup/` (steps: `noise.py` DeepFilterNet 3, `stems.py` Open-Unmix
UMX-HQ, `isolate.py` both in turn, `dereverb.py` the engine's DSP), driven through a Sound document: clip fields
`denoise`, `dereverb`, `isolate`, `stem`, `useCleaned`; `clip.split_stems`; `clean_clips.make_clips` (the
`render_cleanup` tool); `compile` plays the cached take; `listen/cleanup.py` (the `look_cleanup` tool) measures.

- `export_umxhq.py`: builds `~/.rostrum/models/umxhq/umxhq.onnx` from the official weights (scratch venv with CPU
  torch + openunmix; the model network maths unchanged, checked 0.0 difference per target).
- `run_proof.py`: the three tests below, through the document. `measure.py`: cold timings and memory, and the 8-bit
  test. Both run under `heavy.ps1 … gpu`.

**Results** in `C:\Users\Sam\.rostrum\waves\results\stage2\sound-cleanup\`:

| What | Files |
|---|---|
| A voice line made noisy and roomy, then cleaned | `voice-original.wav`, `voice-noisy-roomy.wav`, `voice-denoised-only.wav`, `voice-cleaned.wav`, `voice-before-after.png` |
| The P5 voice-over pulled out of its music | `voice-over-on-music.wav`, `voice-over-isolated.wav`, `voice-over-isolated-before-after.png` |
| The P4 expressive cue in four stems | `cue-mix.wav`, `cue-stem-{vocals,drums,bass,other}.wav`, `cue-true-{drums,bass,other}.wav` (the real groups), `cue-stems-levels.png`, `cue-stem-{vocals,drums}-int8.wav` (the 8-bit model, for comparison) |
| Numbers | `measurements.json` (listening checks), `measurements-models.json` (time, memory, 8-bit) |

The numbers, models and licences: `apps/sound/MODELS.md` › Built, Measurements.

**Verdict: pass with conditions.** Noise reduction and dialogue isolation are strong (floor −36 → −79 dB; the
voice-over comes out of the music at 11.6 dB SDR); reverb reduction shortens the room, does not remove it; stems of an
orchestral cue are rough (UMX-HQ learned pop / rock). Conditions: the licence decisions in MODELS.md (UMX-HQ's
academic-only training data; HTDemucs left out); Sam to listen.

## Attribution rows

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| ONNX Runtime (DirectML build) | 1.24.4 | MIT | apps/sound/python (cleanup models) | Python package | yes | Keep the notice | https://github.com/microsoft/onnxruntime |
| DeepFilterNet 3 weights (torchDF ONNX export) | kimtos-labs/denoiser-dfn3 @ 888f33c | MIT OR Apache-2.0 | apps/sound/python (noise reduction, dialogue isolation) | data, downloaded | yes (download) | Keep the notice | https://github.com/Rikorose/DeepFilterNet |
| Open-Unmix UMX-HQ weights (our ONNX export) | Zenodo 3370489 | MIT (trained on MUSDB18-HQ, academic-only data) | apps/sound/python (stems, dialogue isolation) | data | yes (download, hosting tbd) | Keep the notice | https://github.com/sigsep/open-unmix-pytorch |
| onnx | (venv) | Apache-2.0 | proofs only (8-bit test) | Python package | no | None | https://github.com/onnx/onnx |
| PyTorch (CPU), openunmix | 2.14.1, (pip) | BSD-3-Clause, MIT | proofs only (export, scratch venv) | build tool | no | None | https://pytorch.org |
