# P-3D-1 routes: OpenUSD + Hydra + Cycles on Windows without building USD

*2026-10-21. The goal: a Hydra render delegate for Cycles running inside USD, without compiling OpenUSD ourselves on a 16 GB laptop.*

| Route | Has Hydra imaging? | Source build? | Fits Cycles Hydra? | Verdict |
|---|---|---|---|---|
| **(a) Standalone Cycles + Blender's prebuilt library bundle** (chosen) | **Yes.** The bundle's `usd` folder has `imaging`, `usdImaging` headers and the `hdStorm` plugin; USD is one DLL, `usd_ms.dll` (50 MB) | **No** for USD and every library. Only Cycles itself compiles (CMake, MSVC) | **Yes, made for it.** Cycles' own `BUILDING.md` (`make update`) pulls the bundle and its CMake already points at `lib\windows_x64\usd` | Best. Cost: ~7 GB download, 296 MB of it USD |
| **(b) vcpkg `usd` port** | Only if you ask for the `imaging` feature (off by default; it also pulls OpenGL and OpenSubdiv) | **Yes.** The port downloads the USD source and compiles it with CMake | **Poorly.** The port builds with Python **off** (`PXR_ENABLE_PYTHON_SUPPORT=OFF`); Cycles' CMake turns Python on whenever USD is on. Port is at 26.8, which is fine | Not worth it: it is the USD source build we are avoiding |
| **(c) NVIDIA's prebuilt OpenUSD** (developer.nvidia.com/usd) | **Yes**, `usdview` ships in it | No | **Version risk:** the page I saw offered 25.08 with Python 3.12, and Cycles needs USD **25.11 or newer**. Licence for the binaries: I found no written terms; check the download page before relying on it | Fallback only, if (a) fails and a newer build is on offer |
| **(d) `pip install usd-core`** | **No.** The wheel has "the core USD libraries… none of the optional plugins or imaging features" | No | **No.** No Hydra, so no render delegate | Fine for reading and writing scene files in Python (useful for agents). Cannot render |

## Why (a)

- It is the route the Cycles authors document and test; the same bundle builds Blender itself.
- Licences are mostly permissive (see `LICENCES.md`). The bundle also holds GPL libraries (x264, FFTW …) that Cycles does not use, and they must never ship.
- It does not need a USD source build, so it respects the rule "never build OpenUSD from source without the manager's OK".

## Mac route

Same idea: `make update` clones `lib-macos_arm64` (also from projects.blender.org), then CMake builds Cycles with the **Metal** device and the Hydra plugin. Hydra's own Storm viewer on Mac uses Metal. We cannot test it on this Windows laptop; plan it as a later step, on a Mac, and keep CMake options the same. (Intel Macs use `macos_x64`.)

## Sources

- Cycles building notes: `.build\cycles\BUILDING.md` (local clone of https://projects.blender.org/blender/cycles)
- Bundle contents: https://projects.blender.org/blender/lib-windows_x64 (and its `deps.md`)
- vcpkg port: https://github.com/microsoft/vcpkg/blob/master/ports/usd/vcpkg.json and `portfile.cmake`
- NVIDIA OpenUSD downloads: https://developer.nvidia.com/usd, usdview install steps https://docs.nvidia.com/learn-openusd/latest/usdview-install-instructions.html
- usd-core wheel: https://pypi.org/project/usd-core/
