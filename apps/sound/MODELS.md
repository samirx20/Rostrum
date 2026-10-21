# RostrumSound cleanup models: licences and fit (brief P9)

Read on **2026-10-21** (Team Priyam, brief P9, member *models*). Sources: Hugging Face model cards / API
(`license` field), GitHub READMEs and `LICENSE` files, Zenodo record metadata, maintainers' own issue
answers. Nothing was downloaded or run. Where a page does not state a licence, the table says
**not found**; we never guess.

Rule (AGENTS.md): a model ships in our MIT app only if code **and** weights are MIT / Apache-2.0 / BSD /
CC0 / ISC / zlib / MPL-2.0 and nothing forbids commercial use; never GPL / AGPL / non-commercial /
"research only". It must also fit a 4 GB laptop GPU or CPU, ideally through ONNX Runtime from Python.

**Weights with no stated licence are treated as not allowed.** A repo `LICENSE` covers the *code*; a
checkpoint someone put on Google Drive carries no grant at all (all rights reserved by default).

**The training-data question, said plainly** (same stance as `proofs/sound-sfx/MODELS.md`). Whether a
non-commercial term on training data carries over to the trained weights is legally unsettled. We
record the data so Sam can decide. Two cases are *not* just a footnote here:
- **MUSDB18 / MUSDB18-HQ** (the standard training set for open stem separators): its page says "the
  tracks can only be used for academic purposes" (https://sigsep.github.io/datasets/musdb.html), and
  Demucs's author named it as the reason his weights are research-only (below). Any separator trained
  *only* on MUSDB inherits a visible, explicit academic-only data term, even if its Zenodo / HF tag says MIT.
- **Speech sets** (DNS challenge data, VCTK, LibriVox, Voicebank-DEMAND, etc.) are mostly CC-BY, CC0,
  public domain or ODC-By (Microsoft DNS-Challenge README lists per-set licences, incl. DEMAND CC BY-SA 3.0).
  That is a much milder picture than MUSDB.
We never ship training data, only weights.

## 1. Noise reduction

| Model | Code licence (where read) | Weights licence (where read) | Training data | Size | Runs on | Verdict |
|---|---|---|---|---|---|---|
| **DeepFilterNet 2 / 3** (Rikorose/DeepFilterNet; ONNX exports in the repo's `models/`: `DeepFilterNet3_onnx.tar.gz`, `DeepFilterNet3_ll_onnx.tar.gz`, `DeepFilterNet2_onnx.tar.gz`) | **MIT OR Apache-2.0**, "dual-licensed … at your option" (README, https://github.com/Rikorose/DeepFilterNet) | The README says "All code in this repository is dual-licensed" and the pretrained models live in the repo's `models/` folder; **no separate weights licence is stated** in the README or folder listing, so the repo licence is the only grant (https://github.com/Rikorose/DeepFilterNet/tree/main/models). The `kimtos-labs` card also says Intel's OpenVINO build and an MLX build republish the weights as MIT (card text, not independently checked). | The README names no datasets. Papers (secondary; search summaries, DFN3 PDF not readable by our fetcher): DNS4 challenge clean speech (~500 h full-band) and noise (~150 h), VCTK and PTDB oversampled, simulated + DNS RIRs. DNS-Challenge data is licensed per set (CC BY 4.0, CC0, public domain, ODC-By, CC BY-SA 3.0 for DEMAND; https://github.com/microsoft/DNS-Challenge) | DFN3 ONNX 16.1 MB (kimtos export); models are ~2 M params | CPU, real-time factor 0.19 on one notebook CPU thread (paper abstract, https://arxiv.org/abs/2305.08227); no GPU needed | **Allowed** (code and weights under the repo's MIT/Apache grant; mild data note). **Chosen.** Caveat: the weights' own licence is implied by the repo, not written on the model files. |
| **`kimtos-labs/denoiser-dfn3`** (the ONNX export we already have; torchDF path, github.com/grazder/DeepFilterNet) | upstream MIT OR Apache-2.0 (above); the export fork's own licence **not read** | HF API `cardData.license: apache-2.0`, `license_name: mit-or-apache-2.0` (https://huggingface.co/kimtos-labs/denoiser-dfn3). A third party's card — it states the upstream licence, it cannot grant anything beyond it. | not stated on the card | 16,104,687 bytes, one file `denoiser_model.onnx` (created 2026-07-17) | ONNX Runtime CPU / browser | **Allowed with conditions** — correct licence, but a re-host by an unrelated party: prefer exporting it ourselves from the upstream `DeepFilterNet3` files, or pin the sha256 (`fe5eb64f…e7d8c9` per card) and credit DeepFilterNet. The card does not describe input/output tensors or sample rate (DFN is 48 kHz full band); the lead must check. |
| **RNNoise** (xiph/rnnoise) | **BSD-3-Clause** (README sidebar, https://github.com/xiph/rnnoise) | no separate licence stated; weights downloaded by `autogen.sh` from Xiph.Org servers (README) | "trained using only the publicly available datasets listed below" (README): Xiph background / foreground noise files and clean-speech lists in `datasets.txt` | tiny (size not stated; known to be < 100 K params) | CPU, trivially | **Allowed** (weaker quality than DFN3; 48 kHz mono speech only). Simple fallback. |
| GTCRN (Xiaobin-Rong/gtcrn) | **MIT** (LICENSE file, copyright Rong Xiaobin 2024; https://github.com/Xiaobin-Rong/gtcrn/blob/main/LICENSE) | **not found** — checkpoints on Google Drive / Hamburg servers, no licence stated | DNS3 and VCTK-DEMAND (data terms not stated on the page) | 48.2 K params, 33 MMACs/s | CPU, 16 kHz | **Not allowed** (weights licence not found; also 16 kHz only, not full band). |
| Microsoft DNS baseline (NSNet2) | MIT for the repo code (LICENSE-CODE, https://github.com/microsoft/DNS-Challenge) | **not found** for NSNet2 (README gives no model licence) | DNS challenge data | — | — | **Not allowed** (weights licence not found). |
| Open-Unmix `umxse` (Sony speech-enhancement, Voicebank+DEMAND) | MIT (repo) | Zenodo 3786908 licence **not read** | Voicebank+DEMAND | — | — | Not used: stated in README only, quality below DFN3. |
| Resemble Enhance **denoiser stage** (resemble-ai/resemble-enhance; `--denoise_only`) | **MIT** (README/sidebar) | **MIT** (HF `cardData.license: mit`, https://huggingface.co/ResembleAI/resemble-enhance) | "high-quality 44.1 kHz speech data" (card); datasets not named | HF repo has only the stage-2 enhancer checkpoint (`enhancer_stage2/…/mp_rank_00_model_states.pt`); the denoiser weights are not in the file list we read; size not found | PyTorch; GPU recommended | **Allowed with conditions** on licence, but the full tool is **generative** (conditional flow matching restores / bandwidth-extends speech) — it can change timbre. Not chosen. |

## 2. De-reverb

There are no clearly allowed learned dereverberation models. DeepFilterNet is trained with RIR
augmentation (README: dataset type `rir`) but **its README and abstract say nothing about dereverberation**;
whether DFN3's training target is dry speech was not readable in the sources we could fetch — so we do
not claim it dereverberates. Measure it before saying so.

| Model | Code licence | Weights licence | Training data | Size | Runs on | Generative? | Verdict |
|---|---|---|---|---|---|---|---|
| **WPE (nara_wpe)** (fgnt/nara_wpe) | **MIT** (https://github.com/fgnt/nara_wpe) | none — classic signal processing ("Weighted Prediction Error", long-term linear prediction); no weights | none | tiny | CPU, NumPy | No | **Allowed.** Multichannel-designed but has single-channel modes. A classic-DSP cousin of our own late-reverb suppressor, not a model. |
| SGMSE+ (sp-uhh/sgmse, WSJ0+Reverb, EARS-Reverb checkpoints) | **MIT** (README sidebar, https://github.com/sp-uhh/sgmse) | **not found**; Google Drive / Uni Hamburg downloads, no licence stated | WSJ0-REVERB, EARS-Reverb, ReverbFX (WSJ0 is an LDC-licensed corpus; terms not stated on the page) | not stated | PyTorch, GPU; iterative (N=50 steps) | **Yes** (score-based diffusion; "learns to generate clean speech") | **Not allowed** (weights licence not found; WSJ0 data is licensed-only; generative, can alter words). |
| StoRM (sp-uhh) | MIT (same group; **not read** on its own page) | not read | not read | — | — | Yes (diffusion + predictive) | **Not allowed** (not checked; same family, same concerns). |
| VoiceFixer (haoheliu/voicefixer) | **MIT** (https://github.com/haoheliu/voicefixer) | **not found** — checkpoints (restorer, 44.1 kHz vocoder) with no licence stated | not described | — | PyTorch | Vocoder-based (resynthesises the voice) | **Not allowed** (weights licence not found; resynthesis is wrong for dialogue). |
| Resemble Enhance (enhancer) | MIT | **MIT** (HF card) | "high-quality 44.1 kHz speech" (not named) | stage-2 checkpoint size not found | GPU | **Yes** (CFM). README never mentions dereverberation (only RIRs used in training). | **Allowed with conditions** on licence but unsuitable (generative; not a de-reverb tool). |
| UVR / MelBand-RoFormer "DeReverb / DeEcho" checkpoints (anvuew, SUC-DriverOld; listed in ZFTurbo's `pretrained_models.md`) | MIT (training code) | **not found** — only names / SDR in the table; no licence stated | not stated (community / private mixes) | — | PyTorch | Mask-based (not generative) | **Not allowed** (weights licence not found). |

**Answer for the brief:** no learned model is both clearly better and allowed. Keep our own classic
DSP de-reverb (statistical late-reverb suppression) as the tool. A later option is a single-channel WPE
stage if the lead's listening comparison says it beats ours; that needs no model licence.

## 3. Dialogue isolation (voice vs music + effects)

| Model | Code licence (where read) | Weights licence (where read) | Training data | Size | Runs on | Verdict |
|---|---|---|---|---|---|---|
| **BandIt** / BandIt Plus (kwatcharasupat/bandit; speech / music / effects) | **Apache-2.0** (README, https://github.com/kwatcharasupat/bandit) | **CC BY-NC 4.0** — Zenodo record 10160698 `metadata.license: cc-by-nc-4.0`, 23 checkpoints, ~9.7 GB total (https://zenodo.org/records/10160698) | Divide and Remaster (DnR): LibriSpeech + FMA + FSD50K, mixtures themselves **CC BY 4.0** (Zenodo 6949108 / 5574713) | 190 MB – 1 GB per checkpoint; 25.7–82.6 M params | PyTorch GPU/CPU | **Not allowed** — non-commercial weights. (Wrinkle: the README also "asks commercial beneficiaries to consider voluntary contributions" — a request, not a licence, and it does not override the Zenodo licence.) |
| Banquet (query-based, same group) | not read | not read | — | — | — | Not allowed (not verified; assume same non-commercial pattern until read). |
| MDX23C dialogue / community "BandIt Plus" in ZFTurbo | MIT (ZFTurbo's training code) | **not found** (listed only by name and SDR in `docs/pretrained_models.md`) | — | — | — | **Not allowed** (weights licence not found). |
| "Vocals stem" of an allowed separator | — | see section 4 | — | — | — | **Not available** — no allowed separator exists (section 4). Vocals ≠ dialogue anyway: stem models are trained on songs; speech with SFX underneath is a different task. |
| DeepFilterNet 3 | MIT OR Apache-2.0 | as above | as above | 16 MB | CPU | **Allowed — partial.** It removes *noise*, not music. For stationary / low background it can serve as a dialogue cleaner, not a music remover. Say so in the UI. |

**Answer:** no allowed model separates dialogue from music + effects today. The only model made for the
task (BandIt) is non-commercial.

## 4. Stem separation (vocals / drums / bass / other)

| Model | Code licence (where read) | Weights licence (where read) | Training data | Size | Runs on | Verdict |
|---|---|---|---|---|---|---|
| **HTDemucs v4** (facebookresearch/demucs; `htdemucs`, `htdemucs_ft`, `htdemucs_6s`) | **MIT** ("Demucs is released under the MIT license", README; repo archived 2025-01-01, author no longer at Meta; https://github.com/facebookresearch/demucs) | **Maintainer says NOT MIT, research only.** Issue #327 (adefossez, 2022-05-23): "The model weights are not covered by the MIT license, and are provided only for scientific purposes." Issue #508 "Include Models in commercial products?" (adefossez, 2023-08-02, closed): "Weights are provided for research purpose!" Issue #267 (2022-01-04): MUSDB's licence means "the pre-trained weights are mostly usable" for research and "Making a real app of it is out of the scope of those terms." The README says nothing either way. The HF repo `adefossez/HTDemucs` (files `955717e8.safetensors`, `htdemucs.yaml`): **the API returned no `license` field when we read it today**; the card text has no licence statement; HF discussion #1 on that repo, "Is the `license: mit` on these weights intentional?" (3 users, latest asks to confirm commercial use) has **no maintainer reply** (https://huggingface.co/adefossez/HTDemucs/discussions/1). The CC BY-NC 4.0 claim comes only from a third-party ONNX export README (https://huggingface.co/HRSadeghi/demucs-onnx), not from Meta. | `htdemucs`: MUSDB HQ + "800 songs" (not itemised); `mdx`: MUSDB HQ only; `mdx_extra`: extra data incl. MUSDB test set (README). MUSDB: academic use only. | ~80 M params (4 stems, one model); `htdemucs_ft` is a bag of four, 4× that | PyTorch; third-party ONNX exports exist (HRSadeghi/demucs-onnx: fp16, int8). Fits 4 GB with chunked inference; CPU slow | **Not allowed.** The maintainer's explicit statements outrank the HF tag. The best-quality widely used separator, so this is **DECISION** for Sam only if he can get Meta / the author to confirm in writing. |
| **Open-Unmix UMX-HQ** (`umxhq`; sigsep/open-unmix-pytorch) | **MIT** (README, https://github.com/sigsep/open-unmix-pytorch) | **MIT** — Zenodo record 3370489 `metadata.license: mit-license` (https://zenodo.org/records/3370489); record text has no further terms | MUSDB18-HQ (**academic-use-only data**) | 4 × 35.6 MB = 142 MB, ~22 M params | CPU or GPU; small, fits 4 GB easily; ONNX export possible | **Allowed with conditions.** Weights licence is MIT as recorded; the condition is the MUSDB academic-only training-data term (see top). Quality is clearly below HTDemucs / RoFormers (about 6 dB SDR class). **Best allowed candidate for stems.** |
| Open-Unmix **UMX** (`umx`, 16 kHz band-limited) | MIT | **MIT** (Zenodo 3370486) | MUSDB18 (AAC-compressed, 16 kHz cut) | 4 × 35.6 MB | CPU/GPU | Allowed with conditions (as UMX-HQ); the 16 kHz bandwidth makes it unusable for full-band music. Not chosen. |
| Open-Unmix **UMX-L** (`umxl`, default) | MIT | **CC BY-NC-SA 4.0** — Zenodo record 5069601 `metadata.license: cc-by-nc-sa-4.0`; README: "the weights are only licensed for non-commercial use (CC BY-NC-SA 4.0)" | a private stems dataset | 4 × 113 MB | — | **Not allowed** — non-commercial. |
| **Spleeter** (deezer/spleeter; 2 / 4 / 5 stems) | **MIT** (LICENSE, Deezer SA; https://github.com/deezer/spleeter/blob/master/LICENSE) | **not found** — neither the README nor the sources we read name a licence for the pretrained models. The README only says to "make sure you get proper authorization from right owners" before using it on copyrighted songs; Deezer also sells a separate commercial "Spleeter Pro". | Deezer's private catalogue; the JOSS paper says it cannot be released for copyright reasons (secondary: search summary) | ~100–200 MB per model set (not read) | TensorFlow (ONNX conversions exist, **not vetted**) | **Not allowed** (weights licence not found; unlike Open-Unmix we have no written grant). Check Deezer's GitHub release / model files for a licence if Sam wants it, and Deezer's own wording on the models. |
| BS-RoFormer / Mel-Band RoFormer — lucidrains code | **MIT** (README, https://github.com/lucidrains/BS-RoFormer) | no weights in that repo | — | — | — | code only |
| MelBand-RoFormer vocal model (KimberleyJensen / `KimberleyJSN/melbandroformer`) | repo has **no licence stated** (https://github.com/KimberleyJensen/Mel-Band-Roformer-Vocal-Model) | HF `license: mit`, single file `MelBandRoformer.ckpt`, 913 MB (https://huggingface.co/api/models/KimberleyJSN/melbandroformer) | the author's own larger set; credits aufr33, Anjok, bascurtiz; sources and terms not stated | 913 MB | PyTorch GPU; 913 MB checkpoint, would need fp16 / chunking on 4 GB | **Not allowed (unclear)** — an MIT tag by an individual on a vocal model whose training data is undisclosed, in a repo with no licence, built on (likely commercial) music by people who are not the rights holders. We have no basis to trust the tag. Vocals only (no drums/bass). |
| ZFTurbo Music-Source-Separation-Training: BS-RoFormer (viperx), MelBand variants, SCNet, MDX23C, DTTNet, BS Mamba2 … | **MIT** (training code, https://github.com/ZFTurbo/Music-Source-Separation-Training) | **not found** for the released checkpoints (GitHub release notes and `docs/pretrained_models.md` name models and SDR only) | MUSDB18 / MUSDB18-HQ for the "MUSDB-only" ones; the others "Multisong" / private (MVSep) not itemised | 0.2–1+ GB | PyTorch | **Not allowed** (no weights licence; the MUSDB-only ones carry the academic-only data term; the rest have undisclosed data). |
| SCNet (starrytong/SCNet) | **MIT** (README, https://github.com/starrytong/SCNet) | **not found** (Google Drive links, no licence) | "trained on the MUSDB dataset" | — | PyTorch | **Not allowed** (weights licence not found; MUSDB data). |
| MDX-Net (KUIELab/mdx-net) | **MIT** (repo sidebar, https://github.com/kuielab/mdx-net) | **not found** | MUSDB18 (Leaderboard A: no test set; B: with test set) | — | PyTorch/ONNX | **Not allowed** (weights licence not found; MUSDB data). |
| UVR models (Anjok07/ultimatevocalremovergui) | **MIT** (GUI code) | "No separate model license is stated"; README: "please honor the MIT license by providing credit to UVR" (https://github.com/Anjok07/ultimatevocalremovergui). UVR's developers trained "all of the models provided in this package (except for the Demucs v3 and v4 4-stem models)". | not described | — | ONNX / PyTorch | **Not allowed (unclear)** — the README's one line is not a per-model weights licence; training data undisclosed; the bundled Demucs v3/v4 weights are Meta's (research only, above). |

**Summary:** exactly one stem separator has an *explicit written* permissive weights grant plus a usable
size: **Open-Unmix UMX-HQ** (MIT on its Zenodo record). It is trained on MUSDB-HQ, whose own page says
academic use only, and it is clearly below the state of the art.

## Chosen

- **Noise reduction: DeepFilterNet 3** (ONNX, ONNX Runtime on CPU, 48 kHz full band, ~16 MB, real-time on one CPU thread). Code and the repo's pretrained models are MIT OR Apache-2.0; training data is mostly CC-BY / CC0 / public-domain speech and noise. Export from the upstream `DeepFilterNet3` files ourselves rather than relying on the `kimtos-labs` mirror (or pin its sha256). RNNoise (BSD-3) is the simple fallback.
- **De-reverb: none allowed, so our existing classic DSP late-reverb suppressor.** Every learned option is either generative (SGMSE+, StoRM, VoiceFixer, Resemble Enhance: can alter words and timbre), has no weights licence we could find, or both. WPE (nara_wpe, MIT, no weights) is an allowed classic alternative to try in a listening comparison.
- **Dialogue isolation: no single allowed model.** BandIt (the purpose-built one) is CC BY-NC 4.0. **Built (lead's call):** a chain of the two chosen models: UMX-HQ's vocals stem (the voice away from the music), then DeepFilterNet 3 at full strength (what is left that is not speech). It carries UMX-HQ's condition (decision 2). Measured below: it works on our voice-over.
- **Stem separation: Open-Unmix UMX-HQ** (MIT weights per its Zenodo record; ~142 MB; CPU or small GPU), **allowed with conditions** (MUSDB academic-only training data; quality below HTDemucs). If Sam does not accept that condition, stem separation has no allowed model.

## Decisions for Sam

1. **HTDemucs v4 weights.** Primary sources say research only (issues #327, #508, #267, quoted above); the HF repo is tagged MIT on some views, shows no licence field on others, and the HF discussion asking about it has no reply. We treat it as **not allowed**. Only a written statement from the author or Meta would change that. Do you want us to ask (e.g. a reply on the HF discussion or a new GitHub issue), or leave HTDemucs out for good?
2. **MUSDB-trained weights (UMX-HQ).** Accept "weights are MIT, training data was academic-only", as the other tools accept CC-BY-NC-tinged data? Or skip stem separation until a model with cleaner provenance exists?
3. **Weights with no stated licence** (Spleeter, RoFormer, SCNet, MDX-Net, UVR, DeepFilterNet's own files, GTCRN): we treat "code is MIT, weights say nothing" as **not allowed**. DeepFilterNet is the one exception chosen above because its pretrained models sit inside the repo that says all of it is MIT OR Apache-2.0 and a third party republishes them as Apache/MIT. Is that reading acceptable?
4. **Dialogue isolation and de-reverb** have no allowed model. Do you want us to try to contact the BandIt authors (Zenodo CC BY-NC 4.0 weights) about a commercial licence, or train our own on DnR (CC BY 4.0, LibriSpeech + FMA + FSD50K) later?
5. Spleeter: Deezer's repo may carry a licence for the models we could not see (releases tab). Worth a quick check by the lead before dismissing it.

## Built

| Tool | Model file (in `~/.rostrum/models/`) | Bytes | SHA-256 | Cache key engine |
|---|---|---|---|---|
| Noise reduction | `deepfilternet3/denoiser_model.onnx` (torchDF export, from `kimtos-labs/denoiser-dfn3` @ 888f33c) | 16,104,687 | `fe5eb64f…e7d8c9` | `deepfilternet3-torchdf-fe5eb64f@2` |
| Stems | `umxhq/umxhq.onnx`: **our export** of the four UMX-HQ networks (`proofs/sound-cleanup/export_umxhq.py`, Zenodo 3370489 weights, opset 17, any length) | 142,496,426 | `b26b5f5a…863ec9` | `umxhq-onnx-b26b5f5a@1` |
| Dialogue isolation | the two above, in turn | | | `umxhq…+deepfilternet3…` |
| Reverb reduction | none: the engine's `dereverb` (statistical late-reverb suppression, `engine/src/dialogue/dereverb.rs`), now in the contract | | | `rostrum-sound-dereverb@rostrum-sound-schedule/1-1` |

The UMX-HQ export is not published for download (Sam's hosting decision, like the experiment's HTDemucs); `cleanup/models.py` names a missing or wrong-sized file loudly. The STFT and multichannel Wiener filter around the network are our numpy port (`cleanup/spectra.py`).

## Measurements

Laptop: 16 GB RAM, RTX 3050 4 GB. All four steps run on the **CPU** (no GPU memory): DeepFilterNet's 10 ms hops are too small for the GPU to pay off, and UMX-HQ needs 18 s for a minute of music on the CPU. Cold runs (empty cache), each in its own process, 3 CPU threads (`proofs/sound-cleanup/measure.py`, numbers in `C:\Users\Sam\.rostrum\waves\results\stage2\sound-cleanup\measurements-models.json`):

| Step | Audio | Time | Peak process memory |
|---|---|---|---|
| Noise reduction (DeepFilterNet 3) | 25 s mono voice | 5.6 s | 0.16 GB |
| Reverb reduction (engine DSP) | 25 s voice | 1.5 s | 0.10 GB (Python side; the engine is its own small process) |
| Dialogue isolation (UMX-HQ vocals, then DeepFilterNet 3) | 60 s stereo voice-over on music | 38.5 s | 1.51 GB |
| Stems (UMX-HQ) | 60 s stereo cue | 18.0 s | 1.51 GB |

**Our port is exact:** our ONNX + numpy pipeline against Open-Unmix's own PyTorch `umxhq()` on 15 s of the P4 cue: every stem within 106–129 dB (largest sample difference 9e-7).

**Fixed on the way:** DeepFilterNet's output lags its input by 1440 samples (30 ms: its window plus two look-ahead hops), measured by cross-correlation. The experiment's port removed only 480, so its denoised takes played 20 ms late. Now removed in full; `tests/test_cleanup_models.py` guards it (the cache key moved to `@2`, so no old take is reused).

**Quantizing:** UMX-HQ with 8-bit weights (ONNX Runtime dynamic quantization) is 34.5 MB instead of 136 MB but **no faster** (16.9 s vs 15.3 s) and audibly different from the full model (difference vs full: vocals 11.3 dB, drums 5.1 dB, bass 11.9 dB, other 20.1 dB). Kept at full precision; 1.5 GB of RAM is within budget. DeepFilterNet (16 MB) has nothing to gain.

**Listening checks** (`look_cleanup` numbers; `measurements.json` in the results folder):
- Noisy, roomy voice take (a P5 voice line in our own room: RT60 0.8 s, pink noise, 50 Hz hum, a fan, noise 12 dB under the speech), noise reduction 1.0 + reverb reduction 0.7: noise floor −35.7 → −79.2 dB; speech-to-floor gap 18.6 → 55.3 dB; the level after a word ends falls 6.7 → 19.2 dB in 200 ms (less room). Speech level −17.1 → −24.0 dB (noise and room energy gone; a fader brings it back). Against the dry original (scale-invariant SDR) 3.9 dB noisy → 5.6 dB cleaned: the noise is gone; the reverb is shortened, not undone.
- Voice-over on the music (P5): isolated voice against the real voice stem, SDR **11.6 dB**; the music floor (−33.6 dB) becomes silence between lines; one short blip gets through at the 42.5 s hit.
- P4 expressive cue split into four stems, against the real instrument groups rendered by the engine (drums = drums + timpani + hits; bass = contrabass + tuba; other = the rest; no vocals): SDR drums 1.1 dB, bass −3.6 dB, other 4.4 dB; the vocals stem stays 30+ dB down (right: there is no singer). Envelope correlation between stems 0.02–0.55 (bass vs other highest: both follow the same crescendo). **An orchestral cue is far from what UMX-HQ learned (pop / rock):** drums and bass are recognisable but leak. This is the weakest result, and the reason a stronger stem model is worth the licence question (decision 1).


## Audio description — checked 2026-10-21 (P10, research only; nothing downloaded)

Question: is there a model that writes a plain description of a stretch of sound (what is playing, what the room is, what the voice does) with weights we may ship commercially and a size that fits 4 GB GPU / 16 GB RAM? Sources: Hugging Face API cards read today unless noted; "reported" = a news or listing page, not the model file.

| Model | Code licence | Weights licence | Training data terms | Size | Fits 4 GB GPU / 16 GB RAM? | Verdict |
|---|---|---|---|---|---|---|
| **Qwen2-Audio-7B-Instruct** (Qwen/Qwen2-Audio-7B-Instruct) | Apache-2.0 | **Apache-2.0** (`cardData.license`) | not itemised on the card (mixed public and private audio-text sets) | 8.40 B params, BF16, ~16.9 GB on disk | No. About 17 GB in BF16; 4-bit is still ~5 GB, over the GPU, so it would run split with the CPU, slowly | **Licence ok, does not fit.** The only candidate with an Apache grant; the training-data terms are unknown. A cloud or bigger-machine option, not a local default |
| **Kimi-Audio-7B-Instruct** (moonshotai) | MIT | **MIT** (card); it is built on a Qwen2.5 base, so the base's terms would also need checking (not verified) | not itemised | 9.77 B params, BF16, 42.6 GB | No (42.6 GB on disk; even 4-bit ~6 GB) | **Not usable here** (size). An audio chat model, not a captioner |
| **Qwen3-Omni-30B-A3B-Captioner** (Qwen) | Apache-2.0 | card says `license: other`, name apache-2.0 (not read in full) | not itemised | 31.7 B params, 63.4 GB | No | **Not usable here** (size). Purpose-built audio captioner, the closest in kind |
| Qwen2.5-Omni-3B | Apache-2.0 (repo) | reported **Qwen Research License, non-commercial** for the 3 B model (VentureBeat; not read on the model card) | not itemised | ~3–5 B params | Quantised, close, but the licence blocks it | **Not allowed** (reported non-commercial) |
| **Audio Flamingo 2 / 3** (NVIDIA) | MIT (code) | **NVIDIA OneWay Noncommercial** (listings; AF3 also under Qwen Research licence and OpenAI-generated-data terms) | mixed dataset licences | 0.5 B – 7 B | AF2-0.5B would fit | **Not allowed** (non-commercial weights) |
| **CLAP** (LAION `larger_clap_music_and_speech`) | Apache-2.0 | **Apache-2.0** (card) | LAION-Audio-630K, built from many sources with their own terms (not itemised on the card; not checked) | 1.55 GB | Yes, CPU is fine | **Allowed with conditions, but not a describer.** It scores audio against text you supply (tagging / "does this sound like X"). Could back a tag check ("is there crowd noise?") with an agent-written list, not free text. Data terms to check before use |
| **EnCLAP** (snuffy / MiloLab) | MIT | **not stated** (checkpoints linked, no licence found; the GitHub page was not readable today) | AudioCaps (YouTube AudioSet clips) and Clotho (academic terms) | base ~ a few hundred M params | Yes | **Not allowed** (weights licence not found; data terms) |
| **Pengi** (Microsoft) | MIT | **not stated** (Zenodo checkpoints, no licence) | AudioCaps / Clotho class data | ~ a few hundred M params | Probably | **Not allowed** (weights licence not found; data terms) |

**Verdict: nothing qualifies today.** Every model that writes good free text is either too big for 4 GB (the Qwen audio family, Kimi-Audio: 8–32 B parameters) or has non-commercial weights (Audio Flamingo, Qwen2.5-Omni-3B as reported), and the small captioners (EnCLAP, Pengi) have no weights licence and train on academic-only caption sets. `look_describe` (CONVENTIONS § 9) stays unbuilt. What an agent can do instead is already in the measuring tools (`look_loudness`, `look_spectrum`, `look_events`, `look_beats`, `look_pitch`, `look_clash`, `inspect_harmony`), and a person listens for the rest. **Revisit** if (a) a ≤ 3 B audio captioner appears with Apache/MIT weights and itemised data, or (b) Sam accepts a cloud option with his own key (Qwen2-Audio's Apache weights would then run on a rented GPU). Not verified: Qwen2-Audio's training-data terms, CLAP's data terms, the Qwen3-Omni weights licence text.
