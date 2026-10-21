# CARRY_OVER.md — what to take from the experiment, how much, and how

## The archive

- **Folder:** `C:\Users\Sam\Documents\CODE\MOTION-STUDIO`, checked out at tag **`experiment-final`** (commit `da3f2118`, 2026-10-21). Read-only: never commit there.
- **GitHub:** https://github.com/samirx20/choreo, tag `experiment-final`.
- **Read a file at the tag**, even if the folder has changed:
  `git -C C:\Users\Sam\Documents\CODE\MOTION-STUDIO show experiment-final:<path>`
- **Its own guides:** `AGENTS.md` (old rules; most of them are carried into this repo's AGENTS.md), `HANDOFF.md` (state at the end), `docs/README.md` (map of its docs).
- **Its size:** ~455k lines (330k TypeScript, 97k Rust, 13k shader), ~3,700 commits over 5 weeks. **4 of those weeks went into Motion's Design side**; Sound, 3D and the Editor got about a week between them.

## How to copy

1. **Copy files, not history.** This repo starts fresh. Each copy is one commit: `chore(carry): <what> from experiment-final:<path>`.
2. **Copy only what the target app needs.** The experiment was one app, so its shared core (`src/core/dsl`, `ops`, `registry`, `schema`, `inspect`) mixes all four studios. When you copy, strip the other studios' parts (`threeDsl`, `soundDsl`, `editorDsl`, `ops/three` … for a Rostrum2D copy) and any Bevy-only code. Never copy `native/rostrum-3d`.
3. **Fix the base while copying** (AGENTS.md rule 1). Don't carry known special-case patches; the archive's `HANDOFF.md` §6 "Known Open" and `docs/UNTESTED.md` list what was shaky.
4. **Tests come with their code.** Copy only the tests that guard copied code.
5. **Licences come with their code.** Copy the matching entries from the archive's `docs/ATTRIBUTIONS.md` and `native/rostrum-motion/vendor/PATCHES.md`. After any install, regenerate the notices.
6. **Port means rewrite.** For "port" rows below, the archive is the reference for what and why. Write the new code in the target language; don't transliterate line by line.
7. **Log every copy or port** in the table at the bottom of this file.

## The map

Line counts exclude tests. "When" is the stage in docs/PLAN.md › Teams.

### Copy in (it works; keep it)

| Archive path | Lines | What it is | Goes to | Who / when |
|---|---|---|---|---|
| `native/rostrum-motion/src` + `vendor/` (Blitz, Stylo, Parley, anyrender, usvg, with our patches) | 7.5k + 77k vendored | 2D renderer: Blitz layout + Skia on the GPU | `apps/2d/native/` (only after the Blitz vs Chromium proof says keep) | Sam, Stage 2 |
| `src/core/dsl`, `animation`, `registry`, `schema`, `shapes`, `kits`, `links`, `edits`, `media`, `import` — **Motion parts only** | ~25k of 33k | Motion document: DSL, one animation model, property registry, schemas, geometry, value links, edit history, media resolver | `apps/2d/core/` (edit history, links, media → `shared/` if other apps need them) | Sam, Stage 2 |
| `src/core/ops/motion`, `ops/clips`, `ops/links` | 6.2k | Motion operations (every GUI action as an operation) | `apps/2d/core/ops/` | Sam, Stage 2 |
| `src/engine/stage`, `export`, `typography`, `geometry`, `bindings`, `effects`, `puppet`, `lipsync`, `video` | ~23k | Stage renderers, export, type, geometry, bindings, effects, 2D puppets, lip sync, video timing | `apps/2d/engine/` | Sam, Stage 2 |
| `src/engine/perception/motion`, `perception/linter`, `perception/rendered`, `src/core/inspect` (Motion facts) | ~6k + Motion part of 10.6k | Agent "eyes" for motion: motion check, linter, rendered checks, inspection facts | `apps/2d/engine/perception/` | Sam, Stage 2 |
| `mcp/` (motion tools, `craft.js`, `motionFeedback.js`, `frames.js`, `exportJobs.js`, `rpc.js`, `errors.js`), `bin/` (CLI) | ~4k | MCP server and CLI | Motion tools → `apps/2d/mcp/`; the common pattern → `shared/mcp/` | Sam, Stage 2 |
| `native/rostrum-sound/src` + `vendor/` | 19k + 6k vendored | Sound engine (Firewheel for output only, fundsp, our DSP, CLAP/VST3 hosting) | `apps/sound/native/` | Priyam, Stage 2 |
| `src/core/soundDsl`, `src/core/ops/sound`, `src/engine/sound` | 14k | Sound document, operations, schedule (TypeScript decides, engine renders) | `apps/sound/core/` | Priyam, Stage 2 |
| `src/engine/ai/voice*.ts`, `stems*.ts` + `docs/AI_MODELS.md` | part of 4.8k | Qwen3-TTS voice, stem separation, the vetted model list | `apps/sound/`; the model list → `docs/AI_MODELS.md` here | Priyam, Stage 2 |
| `src/core/captions`, `src/engine/captions` | ~1k | Captions (Parakeet / Omnilingual ASR), subtitle formats | `apps/editor/` (port to C++ or keep as a TS service) | Sam, Stage 2 (Editor) |
| `skills/` (motion-design, sound-writing, audio-pass, color-grading, compositing, cut-out-animation, 3d-filmmaking — 76 files) | guides | Agent how-to guides: techniques, not styles | Each guide to its app's `skills/`; update API names as you go | Each app's team, with its app |
| `src/engine/connectors`, `src/engine/assets` | 2.2k | Free asset sources (Poly Haven, ambientCG, Freesound …), off until the user turns them on | `shared/` (library panel) | Sam, Stage 2 |
| `native/rostrum-color` | 12.4k | One colour library: transfer functions, spaces, LUTs, view transforms | Reference for OpenColorIO setup; copy the parts OCIO doesn't cover | Hem / Priyam, Stage 2 |

### Port (rewrite in the new language, the archive as reference)

| Archive path | Lines | What it is | Goes to | Who / when |
|---|---|---|---|---|
| `src/core/ops/editor`, `src/engine/editor`, `src/core/editorDsl`, `src/core/comp`, `src/engine/comp` | ~28k TS | Editor: timeline ops, masks, stabilising, grading, sound buses, compositor | `apps/editor/` (C++) | Sam + Priyam, Stage 2 (Editor) |
| `src/engine/ai` (the rest: masks with SAM 2, mattes, depth, LaMa inpainting, denoise, point / plane tracking, camera solve) | most of 4.8k TS | VFX AI jobs for the compositor | `apps/editor/` (Comp page) | Priyam, Stage 2 (Editor) |
| `native/rostrum-track` | 2.6k Rust | Point tracker, stabilisation analysis, motion fits | `apps/editor/` (C++, or keep as a Rust library behind a C API) | Priyam, Stage 2 |
| `native/rostrum-ofx` | 2.4k Rust | OpenFX host (one plug-in per child process, memory cap, timeout) | `apps/editor/` | Priyam, Stage 2 |
| `native/rostrum-import` | 3.5k Rust | FBX / OBJ (ufbx) and USD import with a "what was dropped" report | `apps/3d/` (C++; ufbx and USD are C/C++ already) | Hem, Stage 2 |
| `src/core/threeDsl`, `src/core/ops/three`, `src/engine/three` | ~64k TS | 3D document, operations, generators built for the camera, materials, characters, simulations, particles | `apps/3d/` (C++ core, Python API) — **port only what the current step needs**, starting with the product / motion-design tools | Hem, Stage 2 |

### Reference only (read, don't copy)

| Archive path | Why read it |
|---|---|
| `src/app` (~38k: the one-window GUI, React in Tauri) and `docs/gui/` | **The web-UI candidate in the GUI shell proof.** Its Viewer gets frames from a server as images, which is why playback reached only ~1–25 fps; the proof must draw the viewport natively or share it on the GPU. If web UI wins, its kit and screens may be copied into `shared/gui-kit/`. |
| `docs/GUI_DESIGN.md` (and §9, Sam's final choices) | Screen design: shared spine, surfaces, inspector-from-schema, Fast / Final, links, context layers |
| `docs/EDIT_MODEL.md`, `docs/MARKERS.md` | The one-document, one-history model and shared markers |
| `docs/NATIVE_ENGINE.md`, `docs/VIDEO_EDITOR.md` | Engine records and lessons |
| `docs/phase0/COLOUR_PIPELINE.md`, `docs/phase0/PRO_REFERENCE_KIT.md` | Colour pipeline (OCIO + ACES), how references were judged side by side |
| `docs/phase3/STANDARDS.md`, `CAMERA_AWARE.md`, `MOTION_DESIGN_3D.md` | Open standards, built-for-the-camera detail, 3D motion-design tools |
| `docs/SOUND_LIBRARY.md`, `docs/OSS_REUSE.md`, `docs/TESTS.md` | Sound sources, the open-source reuse audit, the lean test rules |
| `docs/user/` | User guide style (install, first project, MCP) |
| `native/rostrum-3d` (Bevy) | Only to see how a feature behaved. **Never copy.** |

### Leave behind

Bevy and everything that only exists for it; the old browser GUI (tag `gui-archive` in the archive); one-off scripts in `scripts/` (bench, rename, unihan …) unless a step needs one.

## Team tooling (outside both repos)

`C:\Users\Sam\.rostrum\waves\` holds the manager's tooling: `RULES.md`, `lead-brief.md`, `quota.mjs` (per-account usage probe), `heartbeat.md` (live run log) and `results/` (past round outputs). They still point at the archive's paths and the old team worktrees. **Update them for this repo before the first Stage 1 launch.**

## Log

| Date | What | From (experiment-final) | To | Commit |
|---|---|---|---|---|
| | | | | |
