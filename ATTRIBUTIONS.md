# ATTRIBUTIONS.md

Every third-party library, model, asset source and tool that ships in or is downloaded by Rostrum, with its licence. Add a row whenever you add one, including its own dependencies when they carry their own licence. The experiment's list (`experiment-final:docs/ATTRIBUTIONS.md`) is the starting point for code carried over.

| Name | Version | Licence | Used by | Ships / downloaded on demand |
|---|---|---|---|---|
| Cycles (standalone, with Hydra render delegate) | main @ a456b76 (2026-09) | Apache-2.0 | Rostrum3D renderer; proof P-3D-1 | Proof build; would ship |
| OpenUSD with Hydra imaging (from Blender's lib-windows_x64) | 26.08 | Apache-2.0 (Pixar modified) | Rostrum3D scene + Hydra; P-3D-1 | Proof build; would ship |
| OpenImageIO, OpenEXR, Imath, OpenJPH, OpenColorIO, oneTBB, Embree, OpenSubdiv, OpenPGL, MaterialX, OpenImageDenoise, OpenVDB (DLL only), pugixml, zlib, zstd, libpng, libjpeg-turbo, libwebp, FreeType, Vulkan loader, SYCL runtime (Embree dep), Python | see `proofs/3d-product/LICENCES.md` | Apache-2.0 / BSD / MIT / zlib / MPL-2.0 / PSF | Cycles + USD dependencies; P-3D-1 | Proof build; would ship as DLLs |
| Blender lib-windows_x64 bundle (as a folder) | main, 2026-10 | mixed; contains GPL parts (FFmpeg+x264/x265, FFTW, rubberband, potrace) not linked by Cycles | P-3D-1 build only | Downloaded for the proof; never ships as a folder |
| NVIDIA CUDA 12.9 redist (nvcc, cudart, cccl) | 12.9.1 | NVIDIA CUDA Toolkit EULA (nvcc internal use only) | Compiling Cycles GPU kernels | Build tool only, never ships; shipping compiled kernels needs NVIDIA's OK |
| NVIDIA OptiX headers (optix-dev) | 9.1.0 | NVIDIA SDK licence / BSD-3 per file | Cycles OptiX build | Build-time only, never committed |
