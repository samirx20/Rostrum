# Sound-match check (proof P-SFX)

**Why.** An agent placing effects on a quiet close-up chose takes by catalogue name
("impact.metal-light") and could not hear what it picked. This tool lets it *check*: it scores
each candidate take against a description ("small iron ring tapping a brass plate, close") with
an audio-text model, so takes can be ranked by how they actually sound.

**Model.** `laion/larger_clap_general` (LAION-CLAP, weights Apache-2.0) through Hugging Face
transformers' `ClapModel` (Apache-2.0). Licences for this and the alternatives: `../MODELS.md`.

## What it does
- `rank`: takes × texts → cosine similarity per take, ranked; plus `prob`, a softmax of the
  target text against a set of **contrast texts** (e.g. "wooden knock", "whoosh", "door creak"),
  using the model's own temperature. Raw cosines from CLAP sit in a narrow band (often 0.1–0.5)
  and are not comparable across texts; `prob` answers "is this take more *this* than *those*?".
  `best_other` names the contrast text the take is closest to. Pass `--contrast` to set your
  own; without it a broad default set of everyday sound families is used (`__main__.py`).
- `score`: cosine for each `{path, text, offset?, length?}` pair in a JSON file.
- `eval`: zero-shot accuracy on a labelled set (`eval.py`): for each take, is the best of the
  label texts its true label? Reports top-1, top-3, per-label hits and the commonest confusions.
- Every command prints **one JSON line** with the results, model, device, load / run time and
  **peak memory** (`peak_ram_mb`, `peak_gpu_mb` on CUDA), and releases the model at exit.

## How a take is heard (one place: `audio.py`, `model.py`)
- A take is `file`, or `file@start+length` (seconds), like the catalogue's in-points.
- Mono, resampled to the model's rate (48 kHz), **peak-normalised** (a quiet recording of the
  right sound should score like a loud one).
- CLAP hears 10 s at a time. Takes up to 10 s are used whole; shorter ones are padded with
  **silence** (`--pad silence`, default). `--pad repeat` loops the take instead (CLAP's training
  default) — for a 0.1 s click that turns it into a buzz, which is why silence is the default;
  the eval can compare both.
- Longer takes: 10 s windows with a 5 s hop; the **3 loudest** (by RMS, `--keep`) are embedded
  and their embeddings averaged. Quiet lead-ins and tails then can't drown the event.

## Setup (done once, by member *match*, 2026-10-21)
```powershell
$S = "C:\Users\Sam\.rostrum\waves\scratch\hem-H4-match"
uv venv --python 3.12 "$S\venv"
uv pip install --python "$S\venv\Scripts\python.exe" torch torchaudio --index-url https://download.pytorch.org/whl/cu128
uv pip install --python "$S\venv\Scripts\python.exe" transformers soundfile numpy scipy librosa huggingface_hub safetensors
$env:HF_HOME = "$S\hf"; uvx --from huggingface_hub hf download laion/larger_clap_general
```
Weights: `C:\Users\Sam\.rostrum\waves\scratch\hem-H4-match\hf\` (744 MB). Nothing in the repo.

## Commands for the lead (from `proofs\sound-sfx\`, through the heavy lock)
Set these once in the shell; `HF_HUB_OFFLINE=1` makes a missing weight fail loudly instead of downloading.
```powershell
cd C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\sound-sfx
$S  = "C:\Users\Sam\.rostrum\waves\scratch\hem-H4-match"
$PY = "$S\venv\Scripts\python.exe"
$env:HF_HOME = "$S\hf"; $env:HF_HUB_OFFLINE = "1"; $env:PYTHONIOENCODING = "utf-8"
```
1. Eval (52 takes, 10 labels; ~1 min on GPU after load):
```powershell
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: clap eval" gpu $PY -m match eval match\eval_set.json --device cuda --out "$S\eval_silence.json"
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: clap eval repeat" gpu $PY -m match eval match\eval_set.json --device cuda --pad repeat --out "$S\eval_repeat.json"
```
2. Rank candidate takes for the door close-up (example; add the takes you want compared):
```powershell
$K = "C:\Users\Sam\.rostrum\assets\sounds\kenney-impact\Audio"
pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: clap rank" gpu $PY -m match rank `
  --text "small iron ring tapping a brass plate, close" `
  --contrast "a wooden knock" --contrast "a whoosh" --contrast "a door creaking" --contrast "a heavy metal clang" `
  "$K\impactMetal_light_000.ogg" "$K\impactMetal_light_002.ogg" "$K\impactTin_medium_000.ogg" "$K\impactPlate_light_000.ogg" "$K\impactWood_light_000.ogg"
```
3. Pairs file: `$PY -m match score --pairs pairs.json --device cuda` (same `heavy.ps1 … gpu` wrapper).

CPU works too (`--device cpu`, no GPU slot needed but still a model run → keep it under the lock).
Expected memory: model ~0.8 GB (fp32); GPU peak should stay well under 2 GB with batch 8.

## Rebuild the eval set
`.venv\Scripts\python.exe proofs\sound-sfx\match\make_eval_set.py` (from the worktree root, main
venv; reads the catalogue through `proofs/sound/rsnd/library.py`). Labels and the picked takes are
listed in that file. Labels come from catalogue names only — if one take is always "wrong",
listen to it before blaming the model. The library has no "keys" category, so keys aren't in the set.

## Status
Built. One CPU smoke test (2026-10-21; torch 2.11.0+cu128, transformers 5.20.2): `rank` on two
Kenney takes against "small metal object hitting metal" put the metal take first (cosine 0.124,
prob 0.63) above the wood take (0.053, prob 0.003); load 10 s, run 1 s, peak RAM 1.4 GB.
`score` and `eval` are built, not run. The real eval run is the lead's.

## Attribution rows
| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| LAION-CLAP `laion/larger_clap_general` (weights) | snapshot ada0c23 | Apache-2.0 (training data: LAION-Audio-630K + AudioSet, some clips non-commercial — see `proofs/sound-sfx/MODELS.md`) | `proofs/sound-sfx/match` | model | dev only | Keep the licence and notice | https://huggingface.co/laion/larger_clap_general |
| Hugging Face transformers (+ tokenizers, safetensors, huggingface_hub) | latest at install | Apache-2.0 | `proofs/sound-sfx/match` | Python package | dev only | Keep the notice | https://github.com/huggingface/transformers |
| PyTorch (+ torchaudio) | 2.x, CUDA 12.8 build | BSD-3-Clause | `proofs/sound-sfx/match` | Python package | dev only | Keep the notice | https://pytorch.org |
