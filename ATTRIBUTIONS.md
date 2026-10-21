# ATTRIBUTIONS.md

Every third-party library, model, asset source and tool that ships in or is downloaded by Rostrum, with its licence. Add a row whenever you add one, including its own dependencies when they carry their own licence. The experiment's list (`experiment-final:docs/ATTRIBUTIONS.md`) is the starting point for code carried over.

- **How it's linked:** `static`, `dynamic` (required for LGPL), `separate program`, `vendored source`, `data` or `model`.
- **Ships?** `ships` (inside the installer), `on demand` (downloaded when the user asks), or `dev only` (proofs, build tools, tests; never shipped).
- **What it asks of us:** credit line, keep the notice, offer the LGPL source / allow relinking, and so on.

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| Qt for Python (PySide6, Shiboken6) with Qt 6 | 6.12.0 | LGPL-3.0 (Qt modules used: Core, Gui, Qml, Quick, Multimedia) | `proofs/gui-qt` (GUI proof) | dynamic | dev only | Keep Qt dynamically linked and replaceable; ship the LGPL notice and offer the source | https://pypi.org/project/PySide6/ |
| PyOpenGL | 3.1.10 | BSD-3-Clause | `proofs/gui-qt` (GUI proof) | Python package | dev only | Keep the notice | https://pypi.org/project/PyOpenGL/ |
| pefile | 2024.8.26 | MIT | `proofs/gui-qt` (listing a DLL's imports while wiring USD) | Python package | dev only | Keep the notice | https://pypi.org/project/pefile/ |
| NumPy | 2.5.4 | BSD-3-Clause | `proofs/gui-qt` (GUI proof) | Python package | dev only | Keep the notice | https://pypi.org/project/numpy/ |
| FFmpeg libraries bundled in the PySide6 wheel (avcodec, avformat, avutil, swscale) | as shipped in PySide6 6.12.0 | LGPL-2.1+ (Qt's LGPL build) | `proofs/gui-qt` video playback (QtMultimedia FFmpeg backend) | dynamic | dev only | Keep them separate, replaceable DLLs; ship the LGPL notice and offer the source | https://doc.qt.io/qt-6/qtmultimedia-attribution-ffmpeg.html |
| Cycles (standalone, with Hydra render delegate) | main @ a456b76 (2026-09) | Apache-2.0 | Rostrum3D renderer; `proofs/3d-product` | dynamic | dev only (proof); would ship | Keep the notice | https://projects.blender.org/blender/cycles |
| OpenUSD with Hydra imaging (from Blender's lib-windows_x64) | 26.08 | Apache-2.0 (Pixar modified) | Rostrum3D scene + Hydra; `proofs/3d-product`; `proofs/gui-qt` Hydra viewport (its Python 3.13 bindings; namespace `pxrBlender_v26_03`) | dynamic | dev only (proof); would ship | Keep the notice | https://openusd.org |
| OpenImageIO, OpenEXR, Imath, OpenJPH, OpenColorIO, oneTBB, Embree, OpenSubdiv, OpenPGL, MaterialX, OpenImageDenoise, OpenVDB (DLL only), pugixml, zlib, zstd, libpng, libjpeg-turbo, libwebp, FreeType, Vulkan loader, SYCL runtime (Embree dep), Python | see `proofs/3d-product/LICENCES.md` | Apache-2.0 / BSD / MIT / zlib / MPL-2.0 / PSF | Cycles + USD dependencies; `proofs/3d-product` | dynamic | dev only (proof); would ship as DLLs | Keep each notice | `proofs/3d-product/LICENCES.md` |
| Blender lib-windows_x64 bundle (as a folder) | main, 2026-10 | mixed; contains GPL parts (FFmpeg+x264/x265, FFTW, rubberband, potrace) not linked by Cycles | `proofs/3d-product` build only | separate download | dev only; never ships as a folder | GPL parts must never reach the apps | https://projects.blender.org/blender/lib-windows_x64 |
| NVIDIA CUDA 12.9 redist (nvcc, cudart, cccl) | 12.9.1 | NVIDIA CUDA Toolkit EULA (nvcc internal use only) | Compiling Cycles GPU kernels | build tool | dev only; shipping compiled kernels needs NVIDIA's OK (NEEDS_DECISIONS) | Internal use of nvcc only | https://developer.nvidia.com/cuda-toolkit |
| NVIDIA OptiX headers (optix-dev) | 9.1.0 | NVIDIA SDK licence / BSD-3 per file | Cycles OptiX build | build-time headers | dev only; never committed | Keep out of the repo | https://developer.nvidia.com/optix |
| PyOpenColorIO (pip `opencolorio`) | 2.6.0 | BSD-3-Clause | OCIO view in proof tools (`proofs/3d-painterly/view.py`) | Python package | dev only | Keep the notice | https://pypi.org/project/opencolorio/ |
| ASWF OCIO "CG config" (`ocio://cg-config-latest`, built into OpenColorIO) | v5.0.0, ACES 2.1, OCIO 2.6 | BSD-3-Clause | Colour management in Cycles and views (`proofs/3d-painterly`) | inside OpenColorIO | would ship | Keep the notice | https://github.com/AcademySoftwareFoundation/OpenColorIO-Config-ACES |
| OpenEXR Python bindings (pip `openexr`) | 3.5.2 | BSD-3-Clause | Reading renders in proof tools (`proofs/3d-product`, `proofs/3d-painterly`) | Python package | dev only | Keep the notice | https://pypi.org/project/OpenEXR/ |
| Pillow | 13.0.0 | MIT-CMU (HPND) | Brush engine and proof tools (`proofs/3d-painterly`) | Python package | dev only | Keep the notice | https://pypi.org/project/pillow/ |
| VSCO 2 Community Edition (Versilian Studios, Sam Gossner) — strings, brass, woodwinds, timpani | 2.x | CC0 1.0 (courtesy credit given) | proofs/sound (P-SND cue) | data | on demand | Keep the notice | see `proofs/sound/LIBRARIES.md` |
| Salamander Grand Piano (Alexander Holm) | V3 | CC BY 3.0 — credit shown | proofs/sound (P-SND cue) | data | on demand | Credit line | see `proofs/sound/LIBRARIES.md` |
| MuldjordKit (DrumGizmo, Lars Muldjord) | 2020-10-18 | CC BY 4.0 — credit shown | proofs/sound (P-SND cue) | data | on demand | Credit line | see `proofs/sound/LIBRARIES.md` |
| Kenney impact / interface / UI / digital sounds | — | CC0 1.0 | proofs/sound (effects pass) | data | on demand | Keep the notice | see `proofs/sound/LIBRARIES.md` |
| Owlish Media sound effects pack | — | CC0 1.0 | proofs/sound (effects pass) | data | on demand | Keep the notice | see `proofs/sound/LIBRARIES.md` |
| BigSoundBank (Joseph Sardin) picks | — | CC0 1.0 (chosen of CC0 / WTFPL / PD) | proofs/sound | data | on demand | Keep the notice | see `proofs/sound/LIBRARIES.md` |
| Freesound CC0 picks (authors in experiment `picks.json`) | — | CC0 1.0 per file | proofs/sound | data | on demand | Keep the notice | see `proofs/sound/LIBRARIES.md` |
| numpy / scipy / soundfile | current | BSD-3-Clause; soundfile bundles libsndfile (LGPL-2.1, dynamic) | proofs/sound (rsnd, listen) | Python package | dev only | Keep LGPL parts dynamic | see `proofs/sound/LIBRARIES.md` |
| librosa | current | ISC (pulls numba BSD, llvmlite BSD+Apache-LLVM, scikit-learn BSD, soxr LGPL-2.1 dynamic, audioread MIT) | proofs/sound/listen | Python package | dev only | Keep LGPL parts dynamic | see `proofs/sound/LIBRARIES.md` |
| pyloudnorm | current | MIT | proofs/sound/listen | Python package | dev only | Keep the notice | see `proofs/sound/LIBRARIES.md` |
| matplotlib | current | PSF-based (BSD-compatible) | proofs/sound/listen | Python package | dev only | Keep the notice | see `proofs/sound/LIBRARIES.md` |
| ACE-Step 1.5 (code; weights acestep-v15-turbo, VAE, text encoder) | 1.5 | MIT (code); weights tagged MIT on Hugging Face (no LICENSE file in the weights repo) | proofs/sound/acestep (tested, not shipped) | model | on demand | Keep the notice | see `proofs/sound/LIBRARIES.md` |
| libepoxy | from Blender lib-windows_x64 (already downloaded in H1) | MIT | `proofs/3d-stylized` (hdRostrum.dll, OpenGL loading) | dynamic (`epoxy-0.dll`) | yes, with Rostrum3D | Keep the MIT notice | https://github.com/anholt/libepoxy |
| LAION-CLAP `laion/larger_clap_general` (weights) | snapshot ada0c23 | Apache-2.0 (training data partly non-commercial, see MODELS.md) | proofs/sound-sfx/match | model | dev only | Keep the licence and notice | https://huggingface.co/laion/larger_clap_general |
| Hugging Face transformers (+ tokenizers, safetensors, huggingface_hub) | 5.20.2 | Apache-2.0 | proofs/sound-sfx/match | Python package | dev only | Keep the notice | https://github.com/huggingface/transformers |
| PyTorch (+ torchaudio) | 2.11.0+cu128 | BSD-3-Clause | proofs/sound-sfx/match | Python package | dev only | Keep the notice | https://pytorch.org |
| OpenCV (opencv-python-headless) | 4.x | Apache-2.0 | proofs/sound-sfx/eyes | Python package | dev only | Keep the notice | https://opencv.org |
| "StiffClothRubbing.wav" by HerbertBoland | Freesound 28297 | CC-BY-4.0 | proofs/sound-sfx redo | sound file | dev only | Credit "HerbertBoland (freesound.org)" | https://freesound.org/people/HerbertBoland/sounds/28297/ |
| "Padlock (SoundAction 005)" by alexarje | Freesound 718103 | CC-BY-4.0 | proofs/sound-sfx redo | sound file | dev only | Credit "alexarje (freesound.org)" | https://freesound.org/people/alexarje/sounds/718103/ |
| "247 - Acoustic Memory - FabricFoley_08.wav" by AcousticMemory | Freesound 371676 | CC-BY-3.0 | proofs/sound-sfx redo | sound file | dev only | Credit "AcousticMemory (freesound.org)" | https://freesound.org/people/AcousticMemory/sounds/371676/ |
| "FingerTapsWoodLongLoop01.wav" by Otakua | Freesound 219933 | CC-BY-3.0 | proofs/sound-sfx redo | sound file | dev only | Credit "Otakua (freesound.org)" | https://freesound.org/people/Otakua/sounds/219933/ |
| 19 CC0 recordings (Freesound, BigSoundBank, OpenGameArt; listed in `effects-20s-redo-takes.json`) | — | CC0-1.0 | proofs/sound-sfx redo | sound files | dev only | Nothing (courtesy credit for BigSoundBank) | see SOURCES.md |
| SciPy | from uv cache | BSD-3-Clause | `proofs/paint/model` (filters) | Python package | dev only | Keep the notice | https://pypi.org/project/scipy/ |
| Blitz (blitz-dom, blitz-paint, blitz-html, blitz-traits; dom and paint patched) | 0.3.0-beta.3 | MIT OR Apache-2.0 | `apps/2d/engine` (layout and paint) | vendored source (dom, paint) + static | ships | Keep the notice | https://github.com/DioxusLabs/blitz |
| AnyRender, anyrender_skia (patched) | 0.14.0, 0.12.0 | MIT OR Apache-2.0 | `apps/2d/engine` (paint API, Skia backend) | vendored source | ships | Keep the notice | https://github.com/DioxusLabs/anyrender |
| Parley (patched), fontique | 0.12.0 | Apache-2.0 OR MIT | `apps/2d/engine` (text layout) | vendored source / static | ships | Keep the notice | https://github.com/linebender/parley |
| usvg (patched) | 0.48.1 | Apache-2.0 OR MIT | `apps/2d/engine` (SVG) | vendored source | ships | Keep the notice | https://github.com/linebender/resvg |
| Stylo (stylo, stylo_traits, selectors, cssparser and the Servo crates) | 0.22.0 | MPL-2.0 | `apps/2d/engine` (CSS) | static | ships | Keep the notice; changes to MPL files stay MPL and their source is offered (we ship them unmodified) | https://github.com/servo/stylo |
| Taffy | 0.15.0 | MIT | `apps/2d/engine` (box layout) | static | ships | Keep the notice | https://github.com/DioxusLabs/taffy |
| skia-safe / skia-bindings, with Skia's prebuilt binaries | 0.153.3 | MIT (bindings), BSD-3-Clause (Skia) | `apps/2d/engine` (GPU paint) | static | ships | Keep both notices | https://github.com/rust-skia/rust-skia |
| skrifa, harfrust (fontations) | 0.44.0, 0.12.0 | MIT OR Apache-2.0, MIT | `apps/2d/engine` (font outlines, shaping) | static | ships | Keep the notice | https://github.com/googlefonts/fontations |
| glutin | 0.32.3 | Apache-2.0 | `apps/2d/engine` (OpenGL context) | static | ships | Keep the notice | https://github.com/rust-windowing/glutin |
| image, png, jpeg-encoder, exr, half | 0.25.10, 0.18.1, 0.7.1, 1.74.2, 2.7.1 | MIT OR Apache-2.0; jpeg-encoder adds IJG; exr BSD-3-Clause | `apps/2d/engine` (picture files) | static | ships | Keep the notices (IJG: credit the Independent JPEG Group) | https://github.com/image-rs |
| ICU4X crates (icu_*, zerovec, yoke …) | 2.3.x | Unicode-3.0 | `apps/2d/engine` (text segmentation, via Parley) | static | ships | Keep the notice | https://github.com/unicode-org/icu4x |
| Roboto Flex | 3.x (archive copy) | SIL OFL 1.1 | `apps/2d/engine/render/tests` (test font) | data | dev only | Keep the OFL text beside it; don't sell the font on its own | https://github.com/googlefonts/roboto-flex |
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
| Recursive | 1.x (archive copy) | SIL OFL 1.1 | `apps/2d/engine/fonts` (app font) | data | ships | Keep the OFL text beside it; don't sell the font on its own | https://github.com/arrowtype/recursive |
| Inter (variable, InterVariable.ttf) | 4.1 | SIL OFL 1.1 | `apps/2d/engine/fonts` (app font) | data | ships | Keep the OFL text beside it; don't sell the font on its own | https://github.com/rsms/inter |
| Qwen3-TTS 1.7B CustomVoice + tokenizer (weights, Q6_K / Q8_0 GGUF) | 12Hz, GGUFs from Serveurperso/Qwen3-TTS-GGUF b7ee2e8 | Apache-2.0 | `apps/sound/python/rostrum_sound/voice.py` | model | yes (downloaded on demand) | Keep the licence and notice | https://huggingface.co/Qwen/Qwen3-TTS-12Hz-1.7B-CustomVoice |
| qwentts.cpp (with GGML) | 01b6127 | MIT | `apps/sound/python/rostrum_sound/voice.py` | separate program | yes (downloaded on demand) | Keep the licence (`LICENSE-qwentts.txt`) | https://github.com/ServeurpersoCom/qwentts.cpp |
| sherpa-onnx (+ sherpa-onnx-core) | 1.13.8 | Apache-2.0 | captions check in this proof | Python package | dev only | Keep the notice | https://github.com/k2-fsa/sherpa-onnx |
| pypdfium2 (+ pdfium) | current | Apache-2.0 / BSD-3 (pdfium: BSD-3) | `apps/2d/python/rostrum2d/io/pdf.py` (PDF import) | Python package (bundles the pdfium DLL) | ships | Keep the notices | https://github.com/pypdfium2-team/pypdfium2 |
| psd-tools | current | MIT | `apps/2d/python/rostrum2d/io/psd.py` (PSD import) | Python package | ships | Keep the notice; check its optional dependencies before shipping | https://github.com/psd-tools/psd-tools |
| gif + color_quant (Rust) | 0.14 / 1.x | MIT OR Apache-2.0 / MIT | `apps/2d/engine/render` (GIF export; not gifski, which is AGPL) | static | ships | Keep the notice | https://github.com/image-rs/image-gif |
| png (Rust) | 0.18 | MIT OR Apache-2.0 | `apps/2d/engine/render` (PNG export, 8 and 16 bit) | static | ships | Keep the notice | https://github.com/image-rs/image-png |
