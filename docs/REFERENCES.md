# REFERENCES.md — where to look things up

## 1. The experiment (archive)

`C:\Users\Sam\Documents\CODE\MOTION-STUDIO`, tag `experiment-final`. What to copy, port or only read is in [CARRY_OVER.md](CARRY_OVER.md). The most useful docs there:

| Need | Archive doc |
|---|---|
| How screens should work (shared spine, inspector-from-schema, Fast / Final, links, context layers; Sam's final §9 choices) | `docs/GUI_DESIGN.md` |
| One document, one history, who changed what | `docs/EDIT_MODEL.md` |
| Shared named markers across apps | `docs/MARKERS.md` |
| Colour pipeline (OpenColorIO + ACES, linear light) | `docs/phase0/COLOUR_PIPELINE.md` |
| Judging against references side by side | `docs/phase0/PRO_REFERENCE_KIT.md` |
| 3D: open standards, built-for-the-camera detail, motion-design tools | `docs/phase3/STANDARDS.md`, `CAMERA_AWARE.md`, `MOTION_DESIGN_3D.md` |
| AI models: the vetted list, sizes, measurements | `docs/AI_MODELS.md` |
| Sound sources and libraries | `docs/SOUND_LIBRARY.md` |
| Open-source reuse audit | `docs/OSS_REUSE.md` |
| Lean test rules | `docs/TESTS.md` |
| Licences of everything used | `docs/ATTRIBUTIONS.md`, `native/rostrum-motion/vendor/PATCHES.md` |
| What was shaky at the end | `HANDOFF.md` §3 and §6, `docs/UNTESTED.md` |
| Agent how-to guides | `skills/` |

## 2. Libraries (Rostrum3D and the Editor)

Check each project's `LICENSE` file before adding it, including its own dependencies, and record it in `ATTRIBUTIONS.md`.

| Library | Use | Licence (as of 2026-10-21) | Where |
|---|---|---|---|
| OpenUSD + Hydra (Storm) | Scene format, plug-in renderers, fast viewport | Apache-based (TOST) | github.com/PixarAnimationStudios/OpenUSD |
| Cycles (+ its Hydra delegate) | Final renderer | Apache-2.0 (checked) | projects.blender.org/blender/cycles |
| OpenVDB | Volumes: smoke, fire, clouds | Apache-2.0 since v12, 2025 (checked) | github.com/AcademySoftwareFoundation/openvdb |
| OpenSubdiv | Subdivision surfaces | Apache-based | github.com/PixarAnimationStudios/OpenSubdiv |
| MaterialX | Materials | Apache-2.0 | github.com/AcademySoftwareFoundation/MaterialX |
| OpenColorIO | Colour management | BSD-3 | github.com/AcademySoftwareFoundation/OpenColorIO |
| OpenImageIO | Image files | Apache-2.0 | github.com/AcademySoftwareFoundation/OpenImageIO |
| OpenEXR | Multi-layer render files | BSD-3 | github.com/AcademySoftwareFoundation/openexr |
| Alembic | Moving geometry interchange | BSD | github.com/alembic/alembic |
| Embree | Ray tracing (used by Cycles) | Apache-2.0 | github.com/RenderKit/embree |
| OpenImageDenoise | Denoising | Apache-2.0 | github.com/RenderKit/oidn |
| Jolt Physics | Rigid bodies, destruction | MIT | github.com/jrouwe/JoltPhysics |
| Mantaflow | Smoke and liquids | Apache-2.0 | mantaflow.com |
| Manifold | Booleans | Apache-2.0 | github.com/elalish/manifold |
| xatlas | UV unwrapping | MIT | github.com/jpcy/xatlas |
| ufbx | FBX / OBJ import | MIT | github.com/ufbx/ufbx |
| OpenCV | Tracking (Editor) | Apache-2.0 | opencv.org |
| OpenFX | Plug-in API (Editor) | BSD | openeffects.org |
| FFmpeg | Reading video files | **LGPL build only**, dynamically linked | ffmpeg.org |
| SVT-AV1, libvpx | AV1 / VP9 encoding | BSD | gitlab.com/AOMediaCodec/SVT-AV1, chromium.googlesource.com/webm/libvpx |

**Video encoding:** H.264 / H.265 come from the computer's own encoders (NVIDIA NVENC, AMD AMF, Intel Quick Sync, Apple VideoToolbox), never from GPL x264 / x265. The experiment called a GPL FFmpeg build as a separate program; the apps must not ship it.

**Build them prebuilt where possible** (vcpkg on Windows, Homebrew / vcpkg on Mac). Building OpenUSD from source on this laptop takes hours.

**Sound:** Firewheel (output only), fundsp, CLAP / VST3 hosting are already in the sound engine. Music model: ACE-Step 1.5 (Apache-2.0). Sampled instruments: SFZ, plus free CC0 libraries.

**GPL projects to study, never copy** (clean-room only): Blender (Grease Pencil, EEVEE, geometry nodes, sculpt, rigging), Goo Engine (stylized shading), Krita (brush engine).

## 3. The reference set (quality yardstick)

The list is in [PLAN.md](PLAN.md) › Reference set (Sam edits it). The media itself is **private and never committed**. It lives on Sam's machine at `C:\Users\Sam\.rostrum\references\<app>\`, one folder per reference, each with a `moments.md` naming the frames, moves and sound cues to match. Proof and app results are compared against these side by side; Sam judges.

## 4. How the studios work (from published interviews)

- **The Windshield Wiper** (Pinkman.TV): Maya, ZBrush, Marvelous Designer, Photoshop / After Effects / Premiere; all backgrounds painted by Alberto Mielgo; keyframe animation; custom tools to shape each character's silhouette shot by shot. Source: Post Magazine interview with producer / CG supervisor Leo Sanchez.
- **Arcane** (Fortiche): Maya, Houdini, Substance Painter, After Effects; heavy hand painting (reportedly 3D-Coat). Renderer not publicly confirmed.
- **Guilty Gear Strive** (Arc System Works): a game engine with custom toon shaders and hand-edited normals.
