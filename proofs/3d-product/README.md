# P-3D-1 · Product still through USD + Hydra + Cycles

**Question:** can we render an Apple-level product shot (glass, anodized aluminium, studio light, real lens with depth of field) through OpenUSD + Hydra + Cycles on this laptop (RTX 3050 4 GB, 16 GB RAM, Windows)?

**Verdict so far: pass with conditions.** The pipeline works and is fast: a 1080p still of our own device in 84 s on the GPU, 0.8 GB of the 4 GB video memory, no OpenUSD source build. The picture is clean and physically right (glass, polished and anodized metal, real depth of field), but it does not yet reach the iPhone Pro film's level: what is missing is look tools (surface texture, brushed metal, a proper view transform) and lighting craft, not render power. Details under "Judged against the quality bar".

## Result (private, not in the repo)

| File | What |
|---|---|
| `C:\Users\Sam\.rostrum\waves\results\stage1\p-3d-1\product-still-1080p.png` | the still, 1920×1080, tone-mapped for viewing |
| `C:\Users\Sam\.rostrum\waves\results\stage1\p-3d-1\product-still-1080p.exr` | the raw render (scene-linear EXR, 23 MB) |
| `C:\Users\Sam\.rostrum\waves\results\stage1\p-3d-1\product-still-1080p.stats.txt` | time, memory, video memory |

No side-by-side with a reference still was made (no press still downloaded); the judgement below is by eye against the iPhone Pro launch film's product close-ups.

## Route chosen and why

**Standalone Cycles** (https://projects.blender.org/blender/cycles, commit `a456b76`, Apache-2.0) built against **Blender's prebuilt Windows library bundle** (`lib-windows_x64`), which contains OpenUSD 26.08 **with Hydra imaging** as one DLL (`usd_ms.dll`). The standalone `cycles.exe` opens a `.usda` and renders it through Cycles' own Hydra render delegate (`src/hydra/file_reader.cpp`: UsdImaging stage scene index → Hydra render index → `HdCyclesDelegate`). The same build also produces `hdCycles.dll`, the Hydra plug-in other USD apps (usdview, our future viewport) load.

Why: it is the route the Cycles authors document, and nothing big is compiled from source: only Cycles itself (9 min). Other routes (`ROUTES.md`): vcpkg's `usd` is a USD source build; NVIDIA's prebuilt USD is older than the 25.11 Cycles needs; pip `usd-core` has no Hydra.

GPU: CUDA kernels for sm_86 (the 3050) and OptiX kernels, compiled with the **CUDA 12.9 compiler from NVIDIA's redistributable zips** (no installer, no admin) and the **OptiX 9.1 headers** from github.com/NVIDIA/optix-dev. Denoising: OpenImageDenoise on the GPU.

## Steps to rebuild (about 35 min, most of it download)

1. `git clone --depth 1 https://projects.blender.org/blender/cycles.git proofs\3d-product\.build\cycles`
2. Library bundle, only the parts Cycles needs (1.7 GB instead of 7 GB): in `.build\cycles`, `python src\cmake\make_update.py` clones `lib\windows_x64`; stop it at the `git lfs pull` step, then in `lib\windows_x64`:
   `git lfs pull --exclude="llvm/**,dpcpp/**,osl/**,manifold/**,alembic/**,draco/**,ceres/**,openvdb/**,rubberband/**,ffmpeg/**,fftw3/**,gmp/**,potrace/**,sndfile/**,openal/**,aom/**,haru/**,xr_openxr_sdk/**,shaderc/**,vulkan/**,hiprt/**,level-zero/**,thorvg/**,tracy/**,Fribidi/**"`
   then `git lfs pull -I "dpcpp/lib/sycl8.lib,dpcpp/bin/sycl8.dll,dpcpp/bin/ur_*.dll,dpcpp/bin/xptifw.dll,openvdb/bin/**,vulkan/bin/vulkan-1.dll"` (Embree links the SYCL runtime; USD needs `openvdb.dll` and `vulkan-1.dll` at run time).
3. CUDA compiler: unzip `cuda_nvcc`, `cuda_cudart`, `cuda_cccl` 12.9 from https://developer.download.nvidia.com/compute/cuda/redist/ into `C:\Users\Sam\.rostrum\tools\cuda-12.9`. OptiX headers: `include\` of https://github.com/NVIDIA/optix-dev into `C:\Users\Sam\.rostrum\tools\optix-9.1`.
4. Apply `cycles-standalone.patch` to `.build\cycles` (adds `--denoise`, and sizes the camera before the USD file is read so 16:9 renders are not squeezed).
5. Build through the lock: `pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: cycles build" build cmd.exe /c C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-product\build.bat`. Then copy `openvdb.dll` and `vulkan-1.dll` from the bundle into `.build\cycles\install\` (the install step does not).
6. Scene: `python -I scene\make_scene.py` writes `scene\product.usda` (see `scene\NOTES.md`).
7. Render: `pwsh -File C:\Users\Sam\.rostrum\waves\heavy.ps1 run "hem: render" gpu pwsh -File C:\Users\Sam\.t3\worktrees\Rostrum\team-hem\proofs\3d-product\render.ps1 <stage.usda> <out.exr> 512 OPTIX 1920 1080`, then `uv run --with openexr --with numpy --with pillow python -I tonemap.py <out.exr> <out.png> --exposure -0.3`. `look.ps1` does both at 960×540 for quick look checks (6 s each).

Build options used: OptiX + CUDA (sm_86 only), OSL **off**, Alembic **off**, OpenVDB volumes **off**, HIP / oneAPI off (all to save build time and download; turn on later as needed).

## Numbers

| | |
|---|---|
| Downloads | Cycles source 30 MB; library bundle 1.7 GB on disk (+1.8 GB git LFS store); CUDA 12.9 compiler zips 133 MB (381 MB unpacked); OptiX headers < 1 MB |
| Disk used | `.build\cycles` ≈ 3.8 GB (lib 1.8, LFS store 1.8, install 0.23); `C:\Users\Sam\.rostrum\tools` 0.38 GB |
| Build time | 9 min for Cycles + Hydra plug-in + sm_86 CUDA and OptiX kernels (`-j 4`) |
| Binary size | `install\` 226 MB (cycles.exe, hdCycles.dll, all DLLs incl. USD 50 MB, kernels) |
| Final render | 1920×1080, 512 samples, OptiX, OIDN on GPU: **84 s** total (scene load and kernel load included) |
| Video memory | **780 MB peak** of 4096 (fits easily) |
| RAM | 2.07 GB peak (cycles.exe) |
| Look renders | 960×540, 64 samples: 6 s, 660 MB video memory |
| How hard on Windows | Medium. Three snags, each a few minutes: CMake needs forward slashes in CUDA paths; three runtime DLLs not covered by the trimmed download (SYCL for Embree, OpenVDB and Vulkan for USD); the standalone app had no denoise switch and fitted the camera before reading the size (both patched). |

## Materials, lights, camera through Hydra

- **Materials:** Cycles' own shader nodes, authored in USD as `UsdShade` shaders with `info:id = "cycles_principled_bsdf"` on the material's `outputs:cycles:surface` (plus a `UsdPreviewSurface` on `outputs:surface` for other viewers). **MaterialX is not converted by this delegate**, so for now Cycles' own nodes are the way; a MaterialX → Cycles step would be our own work (or OSL).
- **Lights:** UsdLux rect and dome lights work as expected (size, intensity, colour temperature).
- **Camera:** UsdGeomCamera focal length, sensor, f-stop and focus distance give real depth of field. The standalone reader takes the first camera in the stage and ignores UsdRender settings.

## Judged against the quality bar (iPhone Pro launch film, product close-ups)

What holds up: the render itself. Glass, polished steel, the machined ridges on the dial and the anodized sides all read as real materials; reflections are clean; depth of field falls off like a real 100 mm lens; no noise after denoising.

What does not yet: (1) surfaces are perfectly smooth: no bead-blasted or brushed texture on the aluminium, no micro-scratches; brushed metal needs UVs and tangents, which the scene does not author yet; (2) lighting is a first setup, not a crafted one: the backdrop reads mid-grey and the side faces get only one soft gradient, where Apple's close-ups use controlled black, long graded highlights and rim light; (3) the view transform is a quick ACES curve in `tonemap.py`, not OpenColorIO (the app writes linear EXR with colour management off); (4) the lens interior is plain; no dispersion or caustic detail. None of these are renderer limits; they are tools we would build (texture and UV tools, a light rig editor, OCIO view transforms) and craft.

**Pass with conditions:** USD + Hydra + Cycles is a sound base for Rostrum3D on this laptop. Condition: the Apple level needs the look tools above; judge again once they exist.

## Licences

See `LICENCES.md`. Everything the built program loads is permissive (Apache-2.0, BSD, MIT, zlib, MPL-2.0, PSF). No GPL DLL is in `install\` (checked: no FFmpeg, x264/x265, FFTW, GMP, libheif, sndfile, potrace, rubberband). The bundle folder itself holds GPL libraries and must never ship as a folder. NVIDIA: `nvcc` is for our internal use only; whether we may ship kernels it compiled, and OptiX in the app, needs NVIDIA's written OK (see **DECISION** in the report).

## What P-3D-2 (painterly still) needs next

- **UVs and textures in the scene path:** author `primvars:st` and connect `cycles_image_texture` nodes (the delegate supports them; untested here); hand-painted textures need this first.
- **OCIO view transform:** set `OCIO` to a config (AgX or ACES) so the app's colour management is on and looks are judged in the right view.
- **Toon / painterly shading:** check which Cycles nodes the delegate exposes for light-driven colour ramps; OSL may be needed (we built with OSL off; turn it on, +260 MB download, longer build).
- **A background card and grain:** a camera-facing textured card is plain USD; grain belongs in the Editor's compositor.
- Same build serves P-3D-3 (`hdCycles.dll` is the Hydra plug-in a stylized delegate would sit beside).
