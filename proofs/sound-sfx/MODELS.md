# Sound-effect models: licences and fit (proof P-SFX)

Read on **2026-10-21** (Team Hem, brief H4, member *match*). Sources: each model's Hugging Face
model card / API (`license` field), the GitHub repo's `LICENSE` or README licence section.
Rule (AGENTS.md): ships in our MIT app only if code **and** weights are MIT / Apache / BSD / CC0 /
CC-BY-like and nothing forbids commercial use; never GPL / AGPL / non-commercial.

**The training-data question, said plainly.** Nearly every open audio model was trained on
mixed public sound collections: AudioSet (YouTube clips), Freesound (each clip under its own
Creative Commons licence, some "non-commercial"), BBC Sound Effects (RemArc licence:
personal / educational / research use only), VGGSound (YouTube), WavCaps / AudioCaps / Clotho.
Those datasets' own pages say "academic use". The *weights* are then released under a licence
of the model maker's choosing. Whether a non-commercial clause on training clips carries over to
the weights is legally unsettled; the common industry reading is that it does not, and only the
weights' own licence binds. We record the data honestly so the manager / Sam can decide; the
verdicts below go by the code and weights licences and by explicit restrictions in the card or
README. **We never ship any training data**, only weights.

## 1. Audio–text models (score a take against a text)

| Model | Code licence | Weights licence (where read) | Training data | Size | Verdict |
|---|---|---|---|---|---|
| **LAION-CLAP `laion/larger_clap_general`** | HF transformers `ClapModel` Apache-2.0; LAION-AI/CLAP repo CC0-1.0 (GitHub API) | **Apache-2.0** (HF card `license: apache-2.0`, https://huggingface.co/laion/larger_clap_general) | LAION-Audio-630K (Freesound incl. CC-BY-NC clips; BBC SFX, RemArc non-commercial; Epidemic Sound; Audiostock; purchased Sonniss / Free To Use Sounds / We Sound Effects / Paramount) + AudioSet with T5 captions; plus music and speech sets. The dataset README says "only academic uses are allowed for LAION-Audio-630K" (https://github.com/LAION-AI/audio-dataset/blob/main/laion-audio-630k/README.md) | 776 MB `.bin`, ~190 M params | **Allowed with conditions** — weights and code are Apache/CC0; condition: training data includes non-commercial clips (see note above). **Chosen for the tool.** |
| LAION-CLAP `laion/clap-htsat-unfused` | same | **Apache-2.0** (HF card) | LAION-Audio-630K + AudioSet (same note) | 615 MB | Allowed with conditions (same). Older, general sounds. |
| LAION-CLAP `laion/clap-htsat-fused` | same | **Apache-2.0** (HF card) | same | ~615 MB | Allowed with conditions. "Fused" handles long takes natively. |
| LAION-CLAP `laion/larger_clap_music`, `larger_clap_music_and_speech` | same | **Apache-2.0** (HF cards) | + music / speech sets | ~776 MB | Allowed with conditions; tuned for music, not foley — not our pick for sound effects. |
| Microsoft CLAP (`msclap`, 2022 / 2023 weights) | **MIT** (github.com/microsoft/CLAP, GitHub API) | **MS-PL** (HF card `license: ms-pl`, https://huggingface.co/microsoft/msclap) | 4.6 M pairs incl. AudioSet, FSD50K, Clotho, AudioCaps, MACS, WavText5K, SoundDescs (= BBC SFX, non-commercial), etc. (from the 2023 paper, from memory — not on the card; the weights' Zenodo copy, record 8378278, licence not checked) | 2023: ~690 MB + GPT-2 text encoder | **Allowed with conditions** — MS-PL is an OSI open-source licence that allows commercial use, but it is not on our list: it requires the MS-PL text to travel with the weights and forbids relicensing them; same training-data note. Second choice; needs the manager's OK to add MS-PL to the list. |
| **Meta PE-AV (Perception Encoder Audio-Visual)** `facebook/pe-av-small/base/large`, `pe-a-frame-*` | **Apache-2.0** (facebookresearch/perception_models, GitHub API); in transformers | **Apache-2.0** (HF cards, "This model is released under the Apache 2.0 license", https://huggingface.co/facebook/pe-av-small) | Meta's large audio-video corpus with synthetic captions (card does not list sources) | small 3.4 GB fp32 (~850 M params), base 4.1 GB, large 8.9 GB; `pe-a-frame-small` 1.8 GB | **Allowed** on licence; card reports state-of-the-art audio-text retrieval and it can also match **video to audio** (useful: score a take against the shot itself). Too big to be our first pick on 16 GB / 4 GB (small would need fp16 ≈ 1.7 GB GPU). **Next to try** if CLAP's eval is weak. Needs a recent transformers. |
| M2D-CLAP (NTT, `nttcslab/m2d`) | NTT licence in a PDF (GitHub API: NOASSERTION) | same NTT licence | AudioSet, WavCaps … | ~ | **Not allowed (unclear)** — the NTT licence is a custom PDF, not one of ours; historically research-only. Don't use unless NTT states a permissive licence. |
| Wav2CLIP (Descript, `descriptinc/lyrebird-wav2clip`) | **MIT** (GitHub API) | MIT (released with the code) | VGGSound (YouTube) | ~ small | Allowed with conditions (VGGSound data note), but weak on text: it maps audio into CLIP's *image* space, so text scores are indirect. Not recommended. |

## 2. Video-to-audio models (generate foley from a shot)

| Model | Code | Weights | Training data | VRAM | Fits 4 GB RTX 3050? | Verdict |
|---|---|---|---|---|---|---|
| MMAudio (hkchengrex) | **MIT** | **CC-BY-NC-4.0** (HF `hkchengrex/MMAudio`; README: "checkpoints … CC-BY-NC 4.0") | AudioSet, Freesound, VGGSound, AudioCaps, WavCaps; README: "We do not guarantee that the pre-trained models are suitable for commercial use" | ~6 GB fp16 (README) | No (6 GB) | **Not allowed** — non-commercial weights. |
| HunyuanVideo-Foley (Tencent) | Tencent Hunyuan Community Licence (GitHub: NOASSERTION) | `license: other`, *tencent-hunyuan-community* (https://huggingface.co/tencent/HunyuanVideo-Foley/blob/main/LICENSE) | Tencent's own large set (not itemised) | XXL 20 GB (12 GB offload), XL 16 GB (8 GB offload) (README) | No | **Not allowed** — custom licence with territory exclusions (EU / UK / South Korea in Hunyuan licences) and user-count limits; not on our list. |
| ThinkSound (FunAudioLLM / Alibaba) | Apache-2.0 header **but** README: "The code, models, and dataset are for research and educational purposes only. Commercial use is NOT permitted." (github.com/FunAudioLLM/ThinkSound README › License) | HF card says `apache-2.0`, contradicted by the README; includes a Stable Audio Open VAE under the **Stability AI Community Licence** ("commercial use and redistribution require prior permission") | VGGSound, AudioCaps, AudioCoT | ~>8 GB (MLLM + 1.3 B audio model) | No | **Not allowed** — explicit no-commercial-use statement and a Stability-licensed part. |
| FoleyCrafter (open-mmlab) | **Apache-2.0** | adapters Apache-2.0 (HF `ymzhang319/FoleyCrafter`) **but** they run on the **Auffusion** base, `license: cc-by-nc-sa-4.0` (HF `auffusion/auffusion-full-no-adapter`) | VGGSound; Auffusion on AudioCaps / WavCaps etc. | ~8–12 GB | No | **Not allowed** — required base model is non-commercial share-alike. |
| Kling-Foley (Kuaishou) | GitHub repo `klingfoley/Kling-Foley`: no licence file found (GitHub API: none) | no weights card found on HF | Kuaishou's own set | — | — | **Not allowed** — no licence = all rights reserved; nothing released we may use. |
| MultiFoley (Adobe / U. Michigan) | research page only | no public weights | VGGSound + licensed SFX | — | — | **Not allowed** — not released. |

**Video-to-audio summary:** none is shippable today, and none fits 4 GB. No "try" flag. The
useful video-aware path we *can* ship is scoring, not generating: PE-AV (Apache-2.0) can embed
the shot's video and a take's audio into one space, so an agent could rank library takes against
the picture itself. That is a later proof, not this one.

## Downloads made for this proof (scratch only, not in the repo)
| Name | Licence | Size | Where |
|---|---|---|---|
| `laion/larger_clap_general` weights + tokenizer | Apache-2.0 | 744 MB | `C:\Users\Sam\.rostrum\waves\scratch\hem-H4-match\hf\` |
| PyTorch (CUDA 12.8 build), torchaudio | BSD-3-Clause | see README | `…\hem-H4-match\venv\` |
| transformers, huggingface_hub, safetensors, tokenizers | Apache-2.0 | small | same venv |
| numpy, scipy, soundfile, librosa | BSD / BSD / BSD-3 / ISC | small | same venv |
