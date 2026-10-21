# P-3D-1 licences: standalone Cycles + Blender's Windows library bundle

*Written 2026-10-21 by a Team Hem member. Sources: the Cycles CMake files (`.build\cycles\src\cmake\`), `deps.md` and the file listing of https://projects.blender.org/blender/lib-windows_x64, and the licence texts linked below. Licence names for third-party libraries come from my knowledge of each project, not from the bundle's own files (the bundle has no per-library licence files that I could find). **Before anything ships, run the check at the bottom ("To verify").***

## Short answer

- The bundle is a **shared Blender folder**, ~7.0 GB on disk, 58 library folders. **Cycles uses only part of it.**
- The bundle **contains GPL code** (x264, x265, FFTW, potrace, rubberband), and LGPL code (GMP, FFmpeg, libsndfile, OpenAL, LAME, libheif, fribidi). **Cycles' own CMake never asks for any of them** (no FFmpeg, FFTW, GMP, potrace or rubberband option in `CMakeLists.txt` or `src\cmake\*.cmake`). They are Blender-only. So a Cycles build does not link them, as far as the CMake shows. One open question: OpenImageIO's own build may pull in LGPL image libraries (libheif) or FFmpeg. See "To verify".
- For the proof, we use the bundle as it is. Nothing is shipped from a proof.
- **NVIDIA pieces are the real licence risk for an MIT app** (OptiX headers, CUDA compiler). See below.

## What Cycles links or ships (from the CMake files)

Sizes are the real file sizes of each folder (the bundle download stores big files as Git LFS pointers; I added up the pointer sizes). Folder = `lib\windows_x64\<folder>`.

| Library | Version (deps.md) | Licence (from my knowledge) | Class | Size | Used by Cycles / Hydra |
|---|---|---|---|---|---|
| OpenUSD (`usd`, monolithic `usd_ms.dll`, includes imaging, `hdStorm`, `usdImaging`) | 26.08 | Apache-2.0 (was "Modified Apache 2.0 / Tomorrow Open Source"; read `LICENSE.txt` in the USD repo) | permissive | 296 MB | Yes, Hydra plugin links it |
| Python | 3.13.13 | PSF | permissive | 277 MB | Yes, required whenever USD is on (`WITH_PYTHON ON`) |
| OpenImageIO | 3.1.16 | Apache-2.0 | permissive | 43 MB | Yes, required |
| OpenEXR + Imath + OpenJPH | 3.4.10 / 3.2.2 / 0.25.2 | BSD-3 / BSD-3 / BSD-2 | permissive | 11 MB + | Yes |
| aom (AV1/AVIF) | 3.13.1 | BSD-2 + patent grant | permissive | 10 MB | Yes (`aom/bin` is bundled with OIIO) |
| OpenColorIO | 2.5.0 | BSD-3 | permissive | 31 MB | Yes, required |
| TBB (oneTBB) | 2022.3.0 | Apache-2.0 | permissive | 16 MB | Yes, required |
| Embree | 4.4.1 | Apache-2.0 | permissive | 68 MB | Yes (CPU ray tracing) |
| OpenShadingLanguage | 1.15.6 | BSD-3 | permissive | 261 MB | Yes (`WITH_CYCLES_OSL` on) |
| LLVM (used by OSL to compile shaders) | 22.1.7 | Apache-2.0 with LLVM exceptions | permissive | 4.35 GB (mostly build-time, static libs) | Linked into OSL; the huge folder is not shipped |
| OpenVDB (+ NanoVDB) | 13.0.0 | MPL-2.0 | permissive (MPL) | 40 MB | Yes (volumes) |
| OpenSubdiv | 3.7.0 | Apache-2.0 | permissive | 26 MB | Yes (subdivision) |
| MaterialX | 1.39.4 | Apache-2.0 | permissive | 193 MB | Yes (USD materials) |
| Alembic | 1.8.3 | BSD-3 | permissive | 91 MB | Yes (`WITH_CYCLES_ALEMBIC` on) |
| OpenPGL (path guiding) | 0.7.1 | Apache-2.0 | permissive | 43 MB | Only if `WITH_CYCLES_PATH_GUIDING` is on |
| OpenImageDenoise (OIDN) | 2.5.0 | Apache-2.0 | permissive | 67 MB | Yes (`openimagedenoise\bin` ships `OpenImageDenoise_device_cuda.dll`, `_cpu`, `_hip`, `_sycl`) |
| Abseil | 20250814.1 | Apache-2.0 | permissive | 77 MB | Pulled in by USD / OpenPGL-era libs |
| pugixml | 1.10 | MIT | permissive | small | Yes (XML) |
| zlib / zstd | 1.3.1 / 1.5.7 | zlib / BSD-3 (zstd is dual BSD or GPLv2; we use it under BSD) | permissive | small | Yes |
| pthreads4w (`pthreadVC3`) | 3.0.0 | Apache-2.0 (since 3.0.0) | permissive | small | Yes (Windows threads) |
| Eigen | 8a1083e | MPL-2.0 | permissive (MPL) | 195 MB (headers) | Build-time headers |
| Boost | n/a | Boost Software Licence | permissive | n/a | Only if USD / OSL ask for it; not in the Windows listing |
| libepoxy | 1.5.10 | MIT | permissive | 3 MB | GUI build only |
| Vulkan headers/loader, shaderc, SPIRV | 1.4.341 / 2025.4 | Apache-2.0 | permissive | 43 MB + 5 MB | USD Vulkan backend (`vulkan/bin` bundled when USD is on) |
| SDL | 3.4.2 | zlib | permissive | 7 MB | Standalone GUI only (off by default) |
| libjpeg-turbo, libpng, libtiff, libwebp, openjpeg, Freetype | 2.1.3 / 1.6.58 / 4.7.1 / 1.6.0 / 2.5.3 / 2.13.3 | BSD / libpng / libtiff / BSD-3 / BSD-2 / FreeType Licence (pick FTL, it is dual with GPLv2) | permissive | small | Through OIDN / OIIO |

**Cycles itself:** Apache-2.0 (`.build\cycles\LICENSE`). Its own `third_party\`: atomic and mikktspace (Apache/BSD-style), cuew and hipew (Apache-2.0), sky (Apache-2.0-compatible Hosek-Wilkie). The `src\cmake\*.cmake` files carry `GPL-2.0-or-later` headers because they are copied from Blender; they are build scripts, not linked code, but note that when we copy them anywhere it carries that header.

## Flagged: GPL / AGPL / LGPL in the bundle

| Library | Version | Licence | In the bundle | Cycles links it? |
|---|---|---|---|---|
| **x264** | 35fe20d | **GPL-2.0+** | inside `ffmpeg` (47 MB) | No: no FFmpeg option in Cycles CMake |
| **x265** | 4.1 | **GPL-2.0** | inside `ffmpeg` | No |
| **FFmpeg** (as built for Blender, with x264/x265) | 8.1 | **GPL-2.0+ build** (LGPL only if built without x264/x265, which this one is not) | `ffmpeg` | No |
| **FFTW** | 3.3.10 | **GPL-2.0+** | `fftw3` (5 MB) | No (Blender compositor only) |
| **potrace** | 1.16 | **GPL-2.0+** | in `deps.md`; no folder listing seen on Windows | No |
| **rubberband** | 4.0.0 | **GPL-2.0+** (commercial alternative exists) | `rubberband` (19 MB) | No (Blender audio only) |
| GMP | 6.3.0 | LGPL-3.0 / GPL-2.0 dual | `gmp` (small) | No (Blender mesh booleans) |
| libsndfile, OpenAL, LAME, libheif, fribidi | 1.2.2 / 1.23.1 / 3.100 / 1.20.2 / 1.0.12 | LGPL-2.1 / LGPL-2.1 / LGPL / LGPL-3 / LGPL-2.1 | various | No, except libheif/FFmpeg possibly through OIIO (verify) |

**Rule for us:** none of these folders may be copied into anything that ships. Only the folders in the first table can.

## NVIDIA pieces (not in the bundle; downloaded separately)

**CUDA toolkit pieces** (https://developer.download.nvidia.com/compute/cuda/redist/, licence: CUDA Toolkit EULA, https://docs.nvidia.com/cuda/eula/index.html)
- Needed by Cycles only to **compile its GPU kernels** (CMake option `WITH_CYCLES_CUDA_BINARIES`, uses `nvcc`) and the OptiX kernels. At run time Cycles loads the NVIDIA driver (`nvcuda.dll`, `nvoptix.dll`) through its own `cuew` loader, so no CUDA toolkit is needed on the user's machine.
- The EULA's redistribution list (Attachment A) names runtime and library files (cudart, cuFFT, cuBLAS, NVRTC, NVVM, libdevice and a few more). **`nvcc` is not on that list**: "Unless a developer tool is identified … as distributable, it is delivered for your internal use only" (EULA 1.1.2). So `nvcc` must not ship.
- The EULA does not say anything about the compiled kernels (PTX / cubin / fatbin) that `nvcc` produces. Blender ships such kernels in every release, so the practice is widespread, but I found no written grant. **Ask `nvidia-compute-license-questions@nvidia.com` before shipping them.**
- The EULA also says you may not use the SDK in a way that makes it subject to an open-source licence needing source disclosure or "free redistribution" (1.2(5)). Our app is MIT, but the compiled kernels are our binaries, not the SDK, so I read this as OK, not certain.
- Size: nvcc + cudart + nvrtc + headers is roughly 1 GB installed (not measured; nothing downloaded yet).

**OptiX headers** (https://github.com/NVIDIA/optix-dev)
- The repo's `LICENSE.txt` is NVIDIA's "SDK, Samples and Tools Licence Agreement (with distribution rights)". `license_info.txt` says each header file is "licensed under either a BSD-3 licence or an NVIDIA Proprietary licence", stated in the file's top comment.
- The agreement allows shipping **binary** products built with them (not the headers themselves), and forbids using the software in a way that would put it under an open-source licence (2.1(xii)). That clause is aimed at shipping NVIDIA code as open source. Compiled OptiX code in our binary is not a problem by itself; **putting the headers in our MIT repo is.**
- So: **headers stay in `.build\`, never committed.** Cycles needs only `OPTIX_ROOT_DIR` at build time.

**OpenImageDenoise** (https://github.com/RenderKit/oidn): Apache-2.0. The pre-trained weights are inside the library; I found no separate weights licence (read the repo `LICENSE.txt` and `weights/` notes before shipping). The CUDA device (`OpenImageDenoise_device_cuda.dll`) needs an NVIDIA driver 528.33+ (Windows) and a Turing or newer card; our RTX 3050 (driver 596.36, compute 8.6) qualifies. It loads the driver only, no toolkit.

## For the apps

| Fine to ship | Proof-only (use, don't ship) | Would need replacing |
|---|---|---|
| Everything in the first table: OpenUSD, OIIO, OCIO, OpenEXR, Embree, TBB, OSL, OpenVDB, OpenSubdiv, MaterialX, OIDN, Alembic, Cycles itself. All Apache / BSD / MIT / zlib / MPL. Ship the DLLs only (no LLVM folder). | The whole bundle as one folder (7 GB). `nvcc`. OptiX headers. The Blender-copied `.cmake` files (GPL-2.0+ headers). | Anything from the GPL list (x264, x265, FFmpeg-as-built, FFTW, potrace, rubberband): we never link them. Our Editor uses LGPL FFmpeg built separately. GMP and libheif only if OIIO turns out to need them: then build OIIO without them. OptiX denoiser / OptiX ray tracing: if the licence reading is a problem, run CUDA (no OptiX) and OIDN for denoising. |

**Open items for Sam / manager:** (1) get written OK on shipping `nvcc`-compiled kernels; (2) decide whether OptiX acceleration ships (faster on RTX, but NVIDIA licence); (3) nothing else blocks the proof.

## To verify (30 seconds, no build)

Once the bundle download finishes, in a Visual Studio prompt:
`dumpbin /dependents lib\windows_x64\OpenImageIO\bin\OpenImageIO.dll` and the same on `usd_ms.dll`, then again on the built `hdCycles.dll`. If `avformat`, `x264`, `fftw`, `heif` or `gmp` appear, tell the manager.

## Draft ATTRIBUTIONS rows

| Name | Version | Licence | Used by | Ships / downloaded on demand |
|---|---|---|---|---|
| Cycles (standalone) | main, Oct 2026 | Apache-2.0 | Rostrum3D renderer (Hydra delegate) | Ships |
| OpenUSD (with imaging, Hydra) | 26.08 | Apache-2.0 (check LICENSE.txt) | Rostrum3D, Editor | Ships |
| OpenImageIO | 3.1.16 | Apache-2.0 | Rostrum3D, Cycles | Ships |
| OpenEXR / Imath / OpenJPH | 3.4.10 / 3.2.2 / 0.25.2 | BSD-3 / BSD-3 / BSD-2 | Rostrum3D, Cycles | Ships |
| OpenColorIO | 2.5.0 | BSD-3 | Rostrum3D, Cycles | Ships |
| oneTBB | 2022.3.0 | Apache-2.0 | Cycles, USD | Ships |
| Embree | 4.4.1 | Apache-2.0 | Cycles (CPU) | Ships |
| OpenShadingLanguage | 1.15.6 | BSD-3 | Cycles | Ships |
| LLVM | 22.1.7 | Apache-2.0 with LLVM exceptions | OSL | Ships (runtime libs only) |
| OpenVDB / NanoVDB | 13.0.0 | MPL-2.0 | Cycles | Ships |
| OpenSubdiv | 3.7.0 | Apache-2.0 | Cycles | Ships |
| MaterialX | 1.39.4 | Apache-2.0 | USD materials | Ships |
| Alembic | 1.8.3 | BSD-3 | Cycles | Ships |
| OpenPGL | 0.7.1 | Apache-2.0 | Cycles (path guiding) | Ships |
| OpenImageDenoise | 2.5.0 | Apache-2.0 | Cycles denoise (CPU + CUDA) | Ships |
| aom | 3.13.1 | BSD-2 + patent grant | OIIO (AVIF) | Ships |
| Python | 3.13.13 | PSF | USD / script layer | Ships |
| pthreads4w | 3.0.0 | Apache-2.0 | Cycles (Windows) | Ships |
| pugixml, fmt, libepoxy, SDL, zlib, zstd, libpng, libjpeg-turbo, libtiff, libwebp, FreeType | see deps.md | MIT, MIT, MIT, zlib, zlib, BSD-3, libpng, BSD/IJG, libtiff, BSD-3, FTL | Cycles / OIIO | Ships |
| Blender lib-windows_x64 bundle | main, Oct 2026 | mixed; contains GPL parts, none linked by Cycles | Proof P-3D-1 only | Downloaded for the proof, never shipped as a folder |
| NVIDIA CUDA toolkit (nvcc, cudart) | 12.x redist | NVIDIA CUDA Toolkit EULA; nvcc internal use only | Compiling Cycles GPU kernels | Downloaded for the proof, nvcc never shipped |
| NVIDIA OptiX headers (optix-dev) | 9.x | NVIDIA SDK licence (with distribution rights) / BSD-3 per file | Cycles OptiX build | Downloaded for the proof, headers never committed |
