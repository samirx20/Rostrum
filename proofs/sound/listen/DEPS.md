# listen — dependencies

Installed with `uv pip install librosa pyloudnorm soundfile matplotlib numpy scipy pytest` into `.venv\` (Python 3.12, Windows). Sizes are what the package takes on disk, measured 2026-10-21. All are permissive; nothing is GPL/AGPL.

## The ones we asked for

| Package | Version | Licence | Size |
|---|---|---|---|
| librosa | 1.0.0 | ISC | 1.1 MB |
| pyloudnorm | 0.2.0 | MIT | <0.1 MB |
| soundfile | 0.14.0 | BSD-3 (wraps libsndfile, LGPL-2.1, shipped as a separate DLL, dynamically loaded) | 2.5 MB |
| matplotlib | 3.11.2 | PSF-based (BSD-compatible) | 23.3 MB |
| scipy | 1.18.1 | BSD-3 | 108.0 MB |
| numpy | 2.5.4 | BSD-3 (plus 0BSD / MIT / zlib parts) | 42.0 MB |
| pytest (test only) | 9.1.1 | MIT | 1.5 MB |

## Pulled in by them (notable)

| Package | Licence | Size | Note |
|---|---|---|---|
| numba | BSD-2 | 12.2 MB | librosa's speed-ups |
| llvmlite | BSD-2 / Apache-2.0 with LLVM exception | 121.5 MB | numba's compiler; the biggest single item |
| scikit-learn | BSD-3 | 27.3 MB | librosa |
| **soxr** | **LGPL-2.1-or-later** | 0.4 MB | librosa's resampler. **LGPL**: it is a compiled Python extension that loads libsoxr as a separate binary, i.e. dynamically linked — allowed by the rules, but list it in ATTRIBUTIONS.md if listen ships. |
| soundfile → libsndfile | LGPL-2.1 | (inside soundfile) | same: separate DLL, dynamically loaded |
| pooch, joblib, lazy-loader, decorator, msgpack, threadpoolctl | BSD / Apache-2.0 | <1 MB each | librosa |
| pillow | MIT-CMU | 14.9 MB | matplotlib |
| fonttools, kiwisolver, contourpy, cycler, pyparsing, python-dateutil, packaging | MIT / BSD / Apache-2.0 | ~13 MB together | matplotlib |
| certifi | MPL-2.0 | 0.2 MB | pooch → requests |
| requests, urllib3, idna, charset-normalizer | Apache-2.0 / MIT / BSD | ~1.7 MB | pooch |
| cffi, pycparser | MIT-0 / BSD | 0.8 MB | soundfile |

`audioread` (MIT) is **not** installed: librosa 1.0 no longer needs it, and `listen` reads files with soundfile only.

**Total ≈ 381 MB** on disk, ~270 MB of it numpy/scipy/llvmlite (shared with anything else in the same venv).

## Licence verdict
No GPL/AGPL. Two LGPL-2.1 pieces (soxr, libsndfile), both separate binaries loaded at run time, which the project rules allow. Everything else is ISC / MIT / BSD / Apache-2.0 / PSF / MPL-2.0.

## Size note for the shipping app
If 381 MB is too big for the installer, the heavy part is llvmlite/numba/scikit-learn (librosa). Only `onsets` (beat tracking) and the spectrogram use librosa; the rest needs just numpy, scipy, soundfile and pyloudnorm. A slimmer build could swap those two for scipy-only code.
