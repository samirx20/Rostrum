# PROOFS.md — Stage 1 briefs

Every foundation choice gets a short proof against a reference before anything is built on it. The proofs answer one question each. They are **throwaway code**: keep each small, in `proofs/<name>/`, with a `README.md` giving the question, setup, result (pictures / sound files with full paths), timings, memory and GPU use, and a verdict (**pass / fail / pass with conditions**).

**Rules for every proof**
- **Time box: 1–3 days.** At the box, report what you have. A proof that can't pass in its box is itself an answer.
- **Judge against the reference.** Results go side by side with the reference moment (`C:\Users\Sam\.rostrum\references\…`). The manager compares first, then Sam decides by eye or ear.
- **Measure on this laptop:** 16 GB RAM, RTX 3050 4 GB, Windows. Note what would differ on a Mac.
- **No app code yet.** Anything worth keeping is rewritten properly in Stage 2.
- Report downloads (name, licence, size).

## Team Hem — 3D

### P-3D-1 · Product still *(first)*
- **Question:** through **USD + Hydra + Cycles**, can we render an Apple-style product shot (glass, anodized aluminium, studio lighting, depth of field) on this laptop?
- **Setup:** OpenUSD and Cycles with its Hydra delegate, prebuilt (vcpkg) where possible. A product model (CC0 or simple modelled) in a USD stage, MaterialX materials, area lights, a real lens. Render through Hydra → Cycles (OptiX on the RTX 3050) with OpenImageDenoise, to EXR.
- **Pass:** side by side with the Apple reference frame, it holds up on screen; a 1080p still in reasonable time; fits in 4 GB VRAM. Also record build time, binary size and how hard the Windows build was.

### P-3D-2 · Painterly still
- **Question:** the same pipeline, with hand-painted textures under real light, a painted background card and grain. Does it read like the Arcane / Pinkman.TV reference still?
- **Pass:** the manager and Sam say it reads like the reference on screen.

### P-3D-3 · Stylized Hydra plug-in spike
- **Question:** can our own Hydra render delegate (raster, GPU) add what Cycles can't: light-to-colour ramps, ink lines with width and taper, brush-stroke shading, and per-shot shape bending?
- **Pass:** a simple shot that reads like the Fortiche / Pinkman.TV reference; renderers swap on the same USD stage without changing the scene.

## Team Priyam — Sound and agent painting

### P-SND · Sound against the reference
- **Question:** do sampled instruments (SFZ / a free orchestral library, plus a CLAP/VST3 instrument through the existing engine), ACE-Step 1.5 and recorded effects, arranged and mixed by an agent, reach the reference soundtrack and effects?
- **Setup:** the archive's sound engine as-is (`experiment-final:native/rostrum-sound`), driven from a small script. One 60-second cue in the spirit of the Arcane score; one 20-second effects pass on a clip (Jibaro / The Witness-style).
- **Pass:** side by side with the reference, not obviously worse (Sam listens). Also: what the agent needed in order to "hear" (spectrogram, loudness, onsets …).

### P-PAINT · Agent painting
- **Question:** with **stroke**, **seeing** and **"where"** tools, can an agent paint a painted background in 2D and, once P-3D-1 renders, a character's or prop's texture in 3D?
- **Setup:** a minimal brush engine (textured brush, pressure, layers, undo) and the agent tools from PLAN.md › "Tools for agents to paint": strokes as point paths, a canvas view at any zoom with a coordinate grid, a reference side by side, before / after, masks. For 3D: screen point ↔ surface point lookup, painting from the camera, and a coverage map.
- **Pass:** it reads like the Arcane / Pinkman.TV reference on screen, and strokes land where the agent meant them. Record the misses and why.

## Team Sam — GUI shell, 2D renderer, repo skeleton

### P-GUI · Web UI vs Qt
- **Question:** can one window hold a Figma-simple UI **and** a live native viewport (Hydra / GPU) and smooth video playback at full speed?
- **Candidates:** (a) the archive's web app (`experiment-final:src/app`, React in Tauri), changed so the viewport is drawn natively or shared on the GPU instead of being sent as images; (b) Qt (LGPL, dynamically linked) with a styled UI.
- **Pass:** smooth (24–60 fps viewport and playback at 1080p), aligned, clicks and keys work, on Windows (Mac noted). Pick the one that holds up and record why.

### P-2D · Blitz vs Chromium (finish)
- **Question:** does the archive's Blitz + Skia renderer hold up on Apple-style reference frames (type, blur, gradients, masks)? Speed and fidelity already passed in the experiment; finish the comparison on the reference set.
- **Pass:** looks right on screen against the reference frames. Note that Blitz is officially pre-alpha; record what we would have to maintain ourselves.

### P-REPO · Repo skeleton and shared-layer contract
- Create the layout in AGENTS.md. Write the **contracts**, not the code: project service (items, markers, live links, cache keys, jobs queue across apps), MCP conventions (run / inspect / edit / render / look), operation and history format. Set up the team worktrees at `C:\Users\Sam\.t3\worktrees\Rostrum\team-<name>`, and update the manager tooling in `C:\Users\Sam\.rostrum\waves\` for this repo.

## Order and the machine

At most two heavy teams at once: Hem (C++ builds, GPU renders) and Priyam (AI models on the GPU) are heavy; Sam is light to medium. P-3D-1 comes first, because P-PAINT's 3D half and the Rostrum2D ↔ 3D link depend on it.
