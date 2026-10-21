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
