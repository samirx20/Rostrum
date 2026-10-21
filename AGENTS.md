# AGENTS.md — Rostrum

Rostrum is four desktop apps for making video, built so **AI agents do the work and a person can do the same in a simple GUI** (Figma-simple, never Blender-cluttered), at top-tier quality (Fortiche, Pinkman.TV, Apple launch films, film-grade sound).

| App | Does | Tech |
|---|---|---|
| **Rostrum2D** | Motion design, type, UI animation, drawing, frame-by-frame, 2D characters | TypeScript document + Rust renderer (Blitz + Skia), carried over from the experiment |
| **RostrumSound** | Music, sound effects, voice, recording, mixing | Rust engine, carried over from the experiment |
| **Rostrum3D** | Modelling, painting, materials, lighting, animation, simulation, rendering | **C++** on USD + Hydra, Cycles and the Academy Software Foundation libraries; **Python** API |
| **Rostrum Editor** | Story, edit, compositing, colour, final mix, delivery | **C++**, sharing the film libraries with 3D; FFmpeg (LGPL) for reading files |

Plus a **shared layer**: project service (items, markers, live links, cache, one jobs queue), GUI kit, painting kit, MCP conventions. Windows + Mac. MIT licence (HireMyLens Media). One installer, pick apps.

## Read first

1. [`HANDOFF.md`](HANDOFF.md) — where things stand right now and what is next.
2. [`docs/PLAN.md`](docs/PLAN.md) — the plan: every decision, each app's full feature list, proofs, teams, references.
3. [`docs/CARRY_OVER.md`](docs/CARRY_OVER.md) — what to take from the experiment, how much, and how.
4. [`docs/REFERENCES.md`](docs/REFERENCES.md) — where to look things up (archive docs, libraries, licences, the reference set).
5. [`docs/PROOFS.md`](docs/PROOFS.md) — Stage 1 briefs, if you are on a proof.
6. [`NEEDS_DECISIONS.md`](NEEDS_DECISIONS.md) — decisions waiting for Sam.

## Where we are

**Stage 1 — Proofs.** Nothing is built in this repo yet. Every foundation choice gets a 1–3 day proof against a reference before anything is built on it. That is the lesson from the experiment, where Bevy was picked untested and had to be thrown away. Do not start app code until the proof it depends on has passed and Sam has seen the result.

## Repo layout (Team Sam creates it in Stage 1)

```
apps/2d/                Rostrum2D
apps/sound/             RostrumSound
apps/3d/                Rostrum3D (C++ core, python/ API)
apps/editor/            Rostrum Editor
shared/project-service/ items, markers, live links, cache, jobs queue
shared/gui-kit/         the one UI kit (shell decided by the GUI proof)
shared/painting-kit/    brush engine + agent painting tools
shared/mcp/             MCP conventions every app follows
proofs/<name>/          Stage 1 proofs: code, results, verdict (README.md)
docs/                   plan, carry-over, references, per-app docs
```

## Rules (binding)

### Working with Sam
- **Sam talks only to the manager** (the coordinating Claude session). Teams never ask Sam directly; questions go to the manager, who settles what it can and brings Sam only real decisions, as multiple-choice questions.
- **Plain language** in everything Sam reads: everyday words, no jargon, full absolute file paths.
- **Tools, not taste.** Build full tools and how-to guides. Never style rules, "anti-slop" lints, look presets passed off as tools, or finished pieces / story templates that agents would copy.
- **Show, don't claim.** Sam judges pictures by eye and sound by ear. A feature list or green tests are not the bar; the reference comparison is.
- Record decisions that are Sam's in `NEEDS_DECISIONS.md` (Open) and keep working on everything they don't block.

### Engineering
1. **Fix the base, not the symptom.** When a bug shows up, find the structural flaw that made that whole class of bug possible and fix it. No narrow special-case `if` patches.
2. **Small and unified.** Prefer < 200 lines per module. Before adding a file, helper or branch, check whether an existing core piece can do it. One source of truth per concept (geometry, timing, colour, media resolution).
3. **The document is the single source of truth.** People (GUI) and agents (script / CLI / MCP) edit the same document. Every change is an operation recorded in one history (undo, versions, who changed what). An agent re-running a script must never wipe what a person moved.
4. **Every GUI action exists first as an operation** an agent can call through MCP / CLI. The GUI is built on those operations, never beside them.
5. **Preview ≡ export.** One render path per app. Frame, storyboard and export render the same way; no preview-only shortcuts.
6. **Fail loudly.** A wait that times out or errors and then carries on is a bug. It must report what failed, never ship a broken file with success.
7. **Analyse once, store as data.** Simulations, tracking, mattes, stem separation and transcripts are computed once on request and stored as editable data or in the content-keyed cache. Renders only read them. The cache key includes the job's engine version.
8. **One compositor, sync by markers.** Frames from different apps are combined only in the Editor. Other apps show the rest of the project as read-only context. Cross-app timing goes through shared, named markers ("logo lands", "drop"), never copied numbers.
9. **One audio engine.** Every sound renders through RostrumSound's engine. 2D and 3D own only sync sound (a cue on a beat, a video's own audio); music, score, voice and sound design live in RostrumSound.
10. **Built for the camera, not a game.** Detail, simulation and render effort go only where the shot's camera sees. Nothing is built for a player who can walk anywhere.
11. **Agents get eyes and ears.** Every app gives agents tools to see or hear their result: frames, contact sheets, motion and loudness checks, "what's here" lookups. Agents paint for real: strokes, seeing the canvas, knowing where each stroke lands.

### Dependencies and licences
- **Reuse open source where it helps**, permissive licences only in what ships: MIT, Apache-2.0, BSD, ISC, zlib, MPL-2.0; LGPL only dynamically linked. **Never GPL / AGPL code or models in the apps.**
- Blender, Goo Engine and other GPL projects may be **studied, never copied**. Use the clean-room method: one agent reads and writes a plain description, a different agent writes our code from that description only.
- Downloads: Sam has given a standing OK for what the work needs, within the licence rule. Report what you downloaded (name, licence, size).
- **AI models:** a fixed, vetted list (local first, cloud optional with the user's own keys), run on the host, loaded on demand, released after the job. Quantize where the loss can't be seen or heard. Record each model's measurements and licence in the models doc.
- Check every new dependency's `LICENSE`, including its own dependencies, and record it in `ATTRIBUTIONS.md`.

### Teams and the machine
- Three teams — **Hem**, **Priyam**, **Sam** — each a lead plus 2–3 members. Their assignments are in docs/PLAN.md › Teams.
- **One permanent worktree per team**: `C:\Users\Sam\.t3\worktrees\Rostrum\team-<name>` on branch `team/<name>`. Members share it and work on separate files; only the lead commits.
- **The laptop:** 16 GB RAM, RTX 3050 (4 GB). At most **2 heavy teams at once**, and **one heavy job per team** (C++ / cargo builds, GPU renders, AI model runs). Members never queue their own heavy jobs; the lead batches them. At most 3 node workers per agent. Agents end the processes they start, by PID.
- **Shared-layer changes** (`shared/`, document schemas, project format) are made by Team Sam, run alone, and merge first.
- Small, time-boxed briefs (~2 h, 2–3 packages). Commit often. Keep a `PROGRESS.md` in the team worktree, deleted in the final commit, so another team can take over on a usage limit.
- Models: Opus for engine and design work, Sonnet for features, Haiku for mechanical work. Medium effort.
- **Tests:** a test earns its place by guarding something users or agents rely on. Per change, run the typecheck plus the tests related to the changed files. Run the full suite once per branch, before reporting. A known-open bug is recorded as a failing-expected test with a `KNOWN OPEN` comment, never deleted.
- **Disk:** 474 GB SSD, ~135 GB free on 2026-10-21. Keep caches capped, clean scratch, and delete a finished worktree's build folders.

### Session handoff
- **`HANDOFF.md` is the single handoff file.** When asked to read the handoff, read it first. When asked to update it, overwrite it in place with what was done and what is next. Never create `HANDOFF_*.md` variants.

### Commits
- Semantic messages (`feat:`, `fix:`, `refactor:`, `test:`, `docs:`, `chore:`). Never skip hooks.
- **Pushing to GitHub** (`origin` = https://github.com/samirx20/Rostrum.git) and any publishing need Sam's OK.
