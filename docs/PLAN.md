# Rostrum: the plan

*Written 2026-10-21, from a conversation with Sam about what the Rostrum experiment taught us and how to reach top-tier quality. **This file is the canonical plan**; Sam's Desktop copy (`C:\Users\Sam\Desktop\Rostrum-Next-Plan.md`) was its first draft. Change decisions here, and only with Sam's say-so.*

In this repo, "the experiment" and "the archive" mean the old repository at `C:\Users\Sam\Documents\CODE\MOTION-STUDIO`, tag `experiment-final` (see [CARRY_OVER.md](CARRY_OVER.md)).

## The goal

- **AI agents do the work**, and everything they do can also be done by a person in a **simple GUI** (like Canva or Figma).
- **Top-tier quality.** For 3D and animation, the bar is Fortiche and Pinkman.TV (Sam's favourites), plus Sony Pictures, DreamWorks and Arc System Works. For motion design, it's Apple product showcases and launch films from billion-dollar companies. For sound, it's both sound effects and soundtrack.
- **We build the tool, not the animation.** AI agents will get better at acting and animation, and when they do, the tool should be ready.

---

## What the experiment was

- **About 5 weeks** of work (16 Sep to 21 Oct 2026). **4 of those weeks were spent on Motion's Design side.** Sound, 3D and the Video Editor got about a week between them, so their quality reflects one week, not a failed idea.
- About **3,700 commits** and **455,000 lines of code** (330k TypeScript, 97k Rust, 13k GPU shader code), about 750 test files and 173 docs.
- A traditional team would need roughly **25–45 engineer-years** for that much code. **Writing code is no longer the slow part.**

### What went wrong

- Everything was crammed into one app.
- We rebuilt engines that already exist (3D renderer, path tracer, liquids) instead of building on proven ones.
- **Bevy was the wrong choice for 3D.** It's a game engine, with no film-quality renderer, no stylized-shading toolkit, and weak rigging and animation tools.
- Sound used synthesized instruments. The sound engine is probably fine; the **sounds going into it** were the weak part.

### What carries over to any stack

- **Stage and beat timeline:** the agent writes what exists, then what happens when (`.then()`, labels, `onHit`).
- **Named markers** for syncing across apps ("logo lands", "drop").
- **One document** that both the agent and the GUI edit, with one undo history.
- **MCP / CLI tools** and the **render a frame, look at it, fix it** loop.
- **Rostrum2D's code**, the most mature part.
- **The Rust sound engine**, plugin hosting (CLAP/VST3), voice (Qwen3-TTS), captions (Parakeet), and the editor's masks and stabilising.

---

## Four separate apps

| App | What it does | Replaces | Tech |
|---|---|---|---|
| **Rostrum2D** | Motion design, typography, UI animation, 2D/2.5D, explainer graphics, **drawing and frame-by-frame animation** | After Effects (+ the drawing side of Toon Boom) | Keep the current TypeScript document and agent tools, plus the renderer (Blitz + Skia). **Note: Blitz is officially pre-alpha**; its heavy parts are mature (Firefox's CSS engine, Chrome's Skia) and it is permissive, so we can keep our own copy. Proof against Chromium decides (see Proofs). |
| **RostrumSound** | Music, sound effects, voice, stems, mixing and mastering | Logic, Pro Tools | Keep the Rust engine. Add sampled instruments, recorded sound libraries and AI models for voice, music and effects. |
| **Rostrum3D** | Modelling, **sculpting**, **texture painting**, materials, lighting, rigging, animation, simulation, cameras, rendering | Blender, Maya, Houdini, Substance Painter / 3D-Coat | **New C++ core on USD + Hydra** (swappable renderers: Storm for the fast viewport, Cycles for final, our own stylized renderer as a plug-in), plus the film-industry libraries (see below). |
| **Rostrum Editor** | Story, cutting, footage, compositing, colour, captions, versions for each platform, final export | Premiere/Resolve plus Nuke | C++, sharing film libraries with 3D (OpenColorIO, OpenImageIO, OpenEXR). FFmpeg (LGPL build, linked separately) for video files. |

**Why the Editor is needed:** it's the only place where 2D, sound, 3D and real camera footage come together into a finished video. It stays separate from Rostrum2D because the two have different kinds of timeline. 2D's animates things inside one shot (like After Effects). The Editor's arranges whole shots and clips (like Premiere).

### Pages in each app

- **Rostrum2D:** Design (including **Draw**) → Animate (including **frame-by-frame**)
- **RostrumSound:** Instruments (including Voice) → Timeline → Mix
- **Rostrum3D:** Build (model, **sculpt**, **paint textures**, place) → Animate (including lip sync and mocap) → Render
- **Rostrum Editor:** Story → Edit → Comp → Colour → Sound → Deliver (→ Review later). Keeps Sam's §9 pages (Edit, Colour, Sound, Deliver) and adds Story and Comp. Its Sound page is levels and mute per clip plus the master mix; anything deeper opens RostrumSound.

Each page does one job, so each stays simple, much like DaVinci Resolve's pages.

### What each app includes (full list)

This merges the new plan with everything the experiment had already decided (its roadmap phases and GUI design), so nothing is dropped by accident.

**Rostrum2D**
- *Design:* vector shapes, pen tool, booleans; type (variable fonts, OpenType features, text on a path); layout (flex / grid, as now); images and video; masks; effects; 2.5D (perspective, tilt); **3D layers live-linked from Rostrum3D** (product renders sit in a 2D piece and update when the 3D changes).
- *Draw:* raster and vector drawing with the shared painting kit; painted backgrounds.
- *Animate:* the beat timeline (as now), keyframes and curve editor, expressions (small code on one item: `bind` / `expr`), stepped timing, smears and trails, world-space camera, frame-by-frame layers, **2D characters** (cut-out puppets, bone rigs, IK — from the experiment's Phase 5), lip sync from Sound's markers.
- *Import:* SVG, PDF (covers Illustrator), PSD layers, Figma (through its API with the user's own token). *Export:* MP4, WebM, GIF, ProRes 4444 with transparency, PNG sequence, Lottie.
- *Agent:* the existing tools (frame, storyboard, motion check, diagnostics).

**RostrumSound**
- *Instruments:* sampled instruments (SFZ, plus any CLAP/VST3 instrument such as Kontakt), free CC0 libraries, synths, drum kits; **Voice** (Qwen3-TTS); **recording from a microphone** (voiceover, foley).
- *Timeline:* audio and MIDI clips (piano roll), tempo and key map, song sections, shared markers; MIDI import / export and MIDI keyboard input; **the project's picture in a corner** at the same moment, so sound is made to picture; sound-effect editing (layering, pitch and time stretch, fades).
- *Sound effects:* recorded libraries (CC0, Freesound connector), AI sound-effect models, procedural effects where they sound good (whooshes, UI clicks).
- *Mix:* buses, sends, effect chains (ours + CLAP/VST3), automation, sidechain, loudness meter and limiter, stems export. Stereo first; 5.1 and Dolby Atmos later.
- *Cleanup:* noise reduction, de-reverb, dialogue isolation and stem separation (vetted models).
- *Agent "ears":* agents read sound through tools that turn it into something they can check — spectrogram images, loudness curves, beat and onset lists, pitch tracks, clash finder, and an AI audio-description model — plus music-theory helpers (keys, chords, voicing).

**Rostrum3D**
- *Build:* polygon modelling (extrude, bevel; booleans via Manifold), subdivision (OpenSubdiv), sculpting, retopology, **UV unwrapping** (xatlas) and baking, texture and projection painting, normal editing, materials (MaterialX node editor with stylized blocks), **text and logo extrusion**, procedural modelling, **cloners and effectors**, world generators built for the camera (street, room, terrain, scatter), **hair and fur** (grooming, including stylized hair cards), cloth garments, lights (product lighting, HDRIs, light linking), cameras (real lenses, depth of field, motion blur, dolly / crane / handheld rigs), several shots per scene. Import: USD, FBX (ufbx), glTF, Alembic, OBJ; CC0 asset connectors.
- *Animate:* keyframes, curve editor, onion skin, pose library, breakdowns, constraints; rigging (auto-rig for humanoids, face rig with ARKit-style shapes), retargeting, mocap libraries and mocap from video, lip sync; per-shot shape bending, stepped timing, smears, drawn lines in 3D; simulations — rigid bodies and destruction (Jolt), cloth, smoke and fire (OpenVDB + Mantaflow), liquids, particles — each computed once and stored as data, and stylizable.
- *Render:* Fast (Storm) / Final (Cycles) / stylized plug-in; render passes; denoising (OpenImageDenoise); EXR out to the Editor.
- *Agent:* Python API + MCP; look tools (shot-camera renders, contact sheets, "what's here", coverage maps, a motion check like 2D's).

**Rostrum Editor**
- *Story:* script, storyboard, colour script.
- *Edit:* timeline (cut, trim, ripple, roll, slip, slide), speed ramps, transitions, live 2D titles, caption track, markers, proxies for heavy media, audio sync by waveform; 2D / 3D / Sound items live-linked — double-click one to open it in its app at that moment, "back to edit" returns.
- *Comp:* node compositor (layer view one click away): keyer, roto with AI masks (SAM 2), tracking (point, planar, camera; OpenCV), cleanup / paint / AI inpainting, depth maps, render passes, paint-over with tracking, comp building blocks, OpenFX plug-ins.
- *Colour:* wheels, curves, HSL qualifiers, power windows, scopes, shot matching, LUTs, ACES.
- *Sound:* levels and mute per clip, the master mix (rendered by the one sound engine).
- *Deliver:* versions per platform, loudness target, MP4 / ProRes / EXR / stems, edit export for Premiere / Resolve.
- *Later:* Review page, multicam, camera RAW formats, HDR delivery.

---

## The shared layer (not an app)

- **Project folder.** Holds the `.mtn`, `.trk`, `.trd` and `.rsm` files, the shared markers and the asset list. Each app opens its own file and the Editor references all of them. Save in one app and the Editor updates.
- **Handing off renders.** 3D and 2D render to **OpenEXR** image sequences with separate layers, so the Editor can adjust shadows or glow without re-rendering. Sound hands over **WAV stems**. A shared cache means nothing renders twice.
- **Colour.** Every app uses **OpenColorIO**, so colours match everywhere.
- **Asset library.** Characters, materials, sounds, fonts and brand kits, as a panel inside every app.
- **Project hub.** A small start screen that opens a project and launches the right app.
- **Agent access.** Every app has an **MCP server** that works the same way: run, inspect, edit, render, look.
- **Painting kit.** One brush engine and one set of painting tools, for people (pen pressure and tilt) and agents (strokes, seeing, locating), used by 2D Draw, 3D texture and projection painting, and the Editor's paint-over. See "Tools for agents to paint".
- **GUI kit.** One shared UI kit so all four apps look and behave alike and stay Figma-simple. **The shell is not decided yet:** web UI (React in a desktop shell) or Qt (what Maya, Houdini, Nuke and Resolve use). A web UI over a native 3D viewport / video playback in one window has no proven recipe in Tauri, so both get a proof first. (Correction: Figma is not "web UI over a native engine"; it runs fully in the browser, drawing into a canvas.)
- **3D file format.** Base `.trd` on **USD**, so scenes also open in Blender, Houdini and Maya.
- **Working with other tools.** Import/export USD, FBX, glTF (3D); send an edit to Premiere/Resolve (Editor); Lottie (2D); stems (Sound). Professionals won't adopt a closed island.
- **"Look" tools for the agent in every app.** 2D has them (storyboard, motion check). 3D (renders from the shot camera, contact sheets), Sound (spectrum, loudness, listening notes) and the Editor (cut, colour and audio checks) get their own.
- **Quality yardstick.** Each app has a set of reference shots / sounds, chosen before building, that it is measured against.
- **AI models.** Local first: vetted open models run on the machine by default. Users can switch on paid cloud models (best music, voice, video) with their own keys.
- **Versions and undo history** for every document.
- **One project, files hidden** (Sam, 2026-10-20, kept): each app shows the project's items in a Project panel; nobody names, saves or hunts for files; saving is automatic.
- **Project service.** A small background program all four apps talk to: project items, markers, live links, the shared cache, and **one jobs queue for the machine** — heavy jobs (renders, simulations, AI models) from every app take turns on the one GPU and the 16 GB of memory.
- **The shared screen parts** (from the experiment's GUI design): one selection that lights up in every view; an inspector built from each operation's definition; a history panel showing who changed what (you, agent, script); a command bar (Ctrl+K); an AI panel where agent changes arrive as a reviewable group and "make variations" gives alternate takes; **Fast / Final** in every viewer; **links between values** (drag a value onto another: tracker → shape, music beat → scale); **context layers** (see the rest of the project, read-only, at the same moment); the dark, clean look (§9).
- **Plug-ins:** CLAP / VST3 (Sound), OpenFX (Editor), Python add-ons (3D), expressions (2D).
- **Guides:** how-to guides for people and agents for every tool. Tools, not taste: no style rules, no finished pieces to copy.
- **Built for the camera** (kept): detail, simulation and render effort go only where the shot's camera sees.
- **One installer** (decided): one download, pick which apps to install; they share the project service, painting kit and models.
- **Video encoding licence note:** the experiment calls a GPL build of FFmpeg as a separate program. In the shipped apps, H.264 / H.265 come from the computer's own encoders (NVIDIA, AMD, Intel, Apple), AV1 from SVT-AV1 (BSD) and WebM from libvpx (BSD), with the LGPL FFmpeg libraries for reading files — no GPL encoders inside, fewer patent-fee questions. Check before release.
- **Later: cloud and heavy rendering.** The same render job, sent to a stronger machine.

---

## Where each missing piece goes

| Missing piece | App | Where in the app | Built on |
|---|---|---|---|
| Script | Editor | **Story** page: the script, split into shots | Plain text in the `.rsm` file |
| Storyboard | Editor | **Story** page: one frame per shot, beside its script line | Quick frames from 2D/3D, or AI sketches |
| Animatic (rough moving version) | Editor | **Cut** page: storyboard frames on the timeline with temporary voice and music | Editor timeline |
| Titles, lower thirds, graphics for the edit | Made in 2D, placed in the Editor | 2D: Design/Animate. Editor: drag onto the timeline; text stays editable | The 2D document, live-linked |
| Voiceover | Sound | **Instruments** page: voice | Qwen3-TTS (exists) |
| Lip sync | 3D (and 2D for 2D characters) | **Animate** page: mouth shapes generated from the voice | Sound hands over word and sound timings as shared markers |
| Mocap from video | 3D | **Animate** page | Pose-detection AI model from the vetted list |
| Live-action footage work (keying, tracking, roto, cleanup, stabilising) | Editor | **Comp** page (node compositor) | GPU nodes, OpenColorIO; existing mask/stabilise code |
| Combining 3D/2D render layers (shadows, glow, depth) | Editor | **Comp** page | OpenEXR layers |
| Colour grading and final look | Editor | **Colour** page | OpenColorIO, GPU grading |
| Captions and subtitles | Editor | **Cut** page: a caption track | Parakeet (exists), editable text |
| Final mix | Sound engine, used from the Editor | Editor: levels and mute per clip. Anything deeper opens in Sound | The one Rust sound engine |
| Loudness for each platform | Sound | **Mix** page: master settings (YouTube about −14 LUFS, broadcast −23) | Loudness meter and limiter in the Rust engine |
| Versions for each platform (16:9, 9:16, 1:1, cutdowns) | Editor | **Deliver** page | Re-framing per version from one source edit |
| Master and export files (MP4, ProRes, EXR, stems) | Editor | **Deliver** page | FFmpeg (LGPL), OpenEXR |
| Hand-painted textures | 3D | **Build** page: paint on the model | Our own paint tools; layers stored with the material |
| Painted backgrounds / matte paintings | 2D (Draw) or 3D (painted cards in the scene) | 2D **Design**, 3D **Build** | Raster painting layers |
| Drawn effects, smears, line work (frame-by-frame) | 2D | **Animate** page: frame-by-frame layer | Drawing tools; placed over 3D in the Editor's Comp page |
| Sculpting and retopology (character creation) | 3D | **Build** page | Our own sculpt tools; OpenSubdiv |
| Per-shot silhouette shaping (bend a character's shape for one camera only) | 3D | **Animate** page, per shot | Shot-specific shape corrections stored with the shot |
| Cloth (clothes that drape and move) | 3D | **Build** (make the garment) and **Animate** (simulate) | Cloth simulation, stored as data once computed |
| Import / export with other tools | Each app | File menu | USD / FBX / glTF, Lottie, edit export for Premiere/Resolve, stems |
| Review and comments (later) | Editor first, then all apps | **Review** page: comments pinned to a frame and time | Comments in the project folder |
| Asset library | Shared layer | A panel in every app | Project folder plus a global library |
| Project hub | Shared layer | Start screen | Reads the project folder |
| Cloud rendering (later) | Shared layer | A "Render" button in 3D and the Editor | Same render job, sent to a stronger machine |

---

## Tools for painterly and stylized work

These are the tools the painterly and stylized studios (Arcane, Pinkman.TV, Spider-Verse, Puss in Boots, Guilty Gear) rely on beyond a standard 3D toolkit. None of them is a filter; they are what artists — and agents — use to make those looks themselves.

**Painting**
1. **One brush engine for 2D and 3D** — textured brushes, pen pressure and tilt, layers. *(Shared painting kit)*
2. **Paint on models in 3D**, in layers. *(3D, Build)*
3. **Projection painting** — paint a background as one picture, wrap it onto simple 3D shapes so the camera can move through it with depth. *(3D, Build)*
4. **Paint over a rendered frame**, with tracking so the paint sticks to moving things. *(Editor, Comp)*

**Controlling light by hand**
5. **Light-to-colour ramps** — choose the painted colour for lit and for shadow instead of physics deciding. *(3D, materials)*
6. **Light linking and shadow shaping** — a light touches only chosen objects; shadows can be moved or painted. *(3D)*
7. **Normal editing** — hand-adjust how light falls across a face. *(3D, Build)*
8. **Material node editor with stylized building blocks** — ramps, halftone, hatching, paper, brush-stroke patterns. *(3D)*

**Lines**
9. **Ink lines from 3D** — outlines and creases with width, wobble and taper. *(3D)*
10. **Draw in 3D space** — hand-drawn lines and shapes attached to 3D objects (a drawn mouth on a 3D face, effects). *(3D, with 2D's drawing tools)*

**Animation tricks from 2D**
11. **Per-shot shape bending** — push a silhouette for one camera only. *(3D, Animate)*
12. **Stepped timing per element** — characters on twos or threes, camera smooth, mixed rates in one shot. *(3D and 2D)*
13. **Smears and multiples** on fast moves. *(3D, Animate)*
14. **Strong keyframe tools** — onion skin in 3D, curve editor, breakdowns, pose library. *(3D, Animate)*

**Effects**
15. **Drawn effects in a 3D scene** — drawn frame by frame in 2D, placed in 3D depth, following the camera. *(2D Draw + 3D)*
16. **Simulations you can stylize** — results simplified, stepped or turned into drawn shapes. *(3D)*

**Finishing**
17. **Render passes** — light, shadow, masks and object IDs as separate layers. *(3D renders, Editor Comp)*
18. **Comp building blocks** — paper and canvas texture, grain, painterly smoothing, edge detection, colour misregistration, lens effects. *(Editor, Comp)*
19. **Colour script** — a board of key frames across the whole film showing colour and mood scene by scene. *(Editor, Story)*

**Directing**
20. **Paint-over notes** — Sam scribbles on a frame ("darker here", "push this pose"); the agent reads the marks and where they are, and adjusts.

## Tools for agents to paint

Agents can paint well, so they paint with the same brushes people use — they just need to **see the canvas and know exactly where each stroke lands**. These are part of the shared painting kit, so they work in 2D Draw, 3D painting and the Editor's paint-over.

**Painting**
- **Strokes** — the agent sends brush strokes: a path of points with pressure, tilt and speed, plus brush, colour, opacity and layer. The same strokes a person makes with a pen, stored as editable strokes and as pixels.
- **Brush test area** — try a brush on a scratch canvas and look before painting for real.
- **Masks** — paint only inside an area (a selection, an object, a material, a face region) so strokes never spill.
- **Layers and undo** — every batch of strokes is one step, undoable; the stroke history is kept.
- **Colour sampling and palettes** — pick colours from the canvas or from a reference; keep a palette.

**Seeing**
- **Look at the canvas** — at any zoom, any region, with an optional coordinate grid drawn over it, so the agent knows exact positions.
- **Look at the model** — the painted model from any view, or through the shot camera, at any zoom.
- **Reference side by side** — a reference image at the same scale beside the work, and a difference view.
- **Before / after** — what the last batch of strokes changed.

**Knowing where (3D)**
- **"What's here"** — a point on screen → which object, which spot on its surface, the texture coordinate, the direction it faces, how far away.
- **The reverse** — a spot on the surface → where it is on screen from this view.
- **Paint from the camera** — strokes drawn on the view are projected onto the surface; the tool reports what each stroke landed on.
- **Coverage map** — which parts of a model are painted, which are not, where the seams are, and which areas the shot camera actually sees (paint what the camera sees first).

**Also available (optional)**
- **AI image models** (local first, cloud optional) to make a starting image or texture, which the agent then paints over and refines with the tools above.

---

## Rostrum3D in detail

### Why C++

Almost all of the film industry's 3D software is C++: Maya, Houdini, Blender and the libraries below. Writing Rostrum3D in C++ lets it use them directly, with no wrappers in between. Agents write C++ well. The costs are a harder Windows build setup and slower compiles.

### What it's built on (no Blender fork)

Blender **uses** these libraries but didn't write most of them. We download them from their own projects, so Blender's GPL never applies.

| Library | What it does | Made by | Licence |
|---|---|---|---|
| Cycles | Film-quality renderer (has a Hydra plug-in) | Blender Foundation (separate project) | Apache-2.0 (checked) |
| OpenVDB | Smoke, clouds, fire | DreamWorks | Apache-2.0 since v12, 2025 (checked) |
| USD | Scene files, the studio standard | Pixar | Apache-based |
| OpenSubdiv | Smooth surfaces | Pixar | Apache-based |
| Alembic | Moving geometry between tools | Sony Pictures Imageworks + ILM | BSD |
| OpenColorIO | Colour management | Sony Pictures Imageworks | BSD |
| OpenImageIO | Image files | Started at Sony Pictures Imageworks | Apache-2.0 |
| OpenEXR | Multi-layer render files | ILM | BSD |
| MaterialX | Material definitions | ILM | Apache-2.0 |
| Embree | Fast ray tracing | Intel | Apache-2.0 |
| OpenImageDenoise | Cleans up noisy renders | Intel | Apache-2.0 |
| Jolt or Bullet | Physics | Jolt / Erwin Coumans | MIT / zlib |
| Mantaflow | Smoke and liquid simulation | TU Munich | Apache-2.0 |

Most are now looked after by the **Academy Software Foundation**, a group run by the film industry. Each licence is in the `LICENSE` file at the top of that project's source. **Check each one before adding it.**

### What we build ourselves

The agent layer, the simple GUI, **stylized shading** (painterly, cel and line-art looks), compositing for the look, sculpting and texture painting, and the character tools: rigging, faces and animation.

### Why USD + Hydra (the anti-Bevy choice)

Hydra is USD's plug-in renderer system. One scene can be drawn by different renderers: **Storm** (fast viewport, comes with USD), **Cycles** (realistic final, already has a Hydra plug-in), and **our stylized renderer** as one more plug-in. Cycles is a realistic renderer: right for product shots and for Fortiche/Pinkman-style painted textures under real light, wrong on its own for cel/anime shading (Arc System Works' Guilty Gear uses a game engine with custom toon shaders). With Hydra, renderers can be swapped, so we are never locked in again.

### What the big studios use (for reference)

Arcane: Maya, Houdini, Substance Painter, After Effects, and heavy hand painting (reportedly 3D-Coat). The renderer isn't publicly confirmed. The look comes mainly from painted textures, painted 2D effects and compositing.

---

## Licences: Blender, GPL and Goo Engine

- **Blender's own code** (Grease Pencil, EEVEE, geometry nodes, modifiers, rigging, sculpting) is **GPL**. Copying it into Rostrum would make the whole app GPL.
- **GPL doesn't forbid selling.** It means anyone who gets the program also gets the source code, may share or change it, and nobody can make it closed. **Goo Engine** (Dillon Goo Studios, a stylized/anime fork of Blender) is sold on Patreon with its source public on GitHub. People pay for builds, early access and support.
- **Learning from Blender and Goo Engine is fine** if done "clean room". One agent reads the code and writes a plain description of how it works. A different agent writes our code from that description only. Translating their code line by line is still copying.
- **Running Blender as a separate program** that our app talks to doesn't make our app GPL.
- **Current direction:** stay **MIT**, use Cycles and the permissive libraries, and don't fork Blender.
- Not legal advice. Have a lawyer check before this becomes a business.

---

## How hard it is

**Easier than the experiment.** Rendering, volumes, colour, file formats, denoising and physics are solved problems, and we plug them in. At the pace already shown, a C++ Rostrum3D on Cycles rendering good-looking scenes is a matter of weeks.

**Still hard (where the quality lives):**
1. **The stylized look.** Arcane's look is custom shading, hand-painted textures, painted 2D effects over 3D, and heavy compositing, not the renderer. Months of work.
2. **Characters.** Models, rigs that bend well, and faces that show emotion.
3. **Acting.** This depends on how good AI agents become. Our job is to make the tool ready for it.
4. **The agent judging its own work.** Telling "fine" from "Fortiche".

**For sound:** professional quality comes from sampled instruments, recorded effect libraries and AI models (e.g. ACE-Step 1.5, Apache-2.0), layered and mixed by the agent. Not from synthesizing real instruments.

---

## Proofs before committing (the lesson from Bevy)

Bevy was chosen before it was tested against the real goal. Rule: **every foundation choice gets a short proof (1–3 days) against the reference before we commit.**

| Proof | Question it answers | Pass when |
|---|---|---|
| GUI shell: web UI vs Qt | Can one window hold a Figma-simple UI **and** a live native 3D viewport / smooth video playback? | Smooth, aligned, clicks work, on Windows and Mac; then pick the one that holds up |
| 3D: product still (first) | Through USD + Hydra + Cycles, can we render an **Apple-style product shot** (glass, anodized aluminium, studio light, depth of field) on the RTX 3050 laptop? | Side by side with the Apple reference frame, it holds up on screen |
| 3D: painterly still | Through USD + Hydra + Cycles, can we render a **painterly** still (hand-painted textures under real light, a painted background, grain) on an RTX 3050 laptop (4 GB)? | Reads like the Arcane / Pinkman.TV reference still on screen, in a reasonable time |
| 3D: stylized plug-in | Can our own Hydra plug-in add what Cycles can't: painted light ramps, brush-stroke shading, line work, per-shot silhouette shaping? | A simple shot that reads like the Fortiche / Pinkman.TV reference |
| Agent painting | With the stroke, seeing and "where" tools, can an agent paint a character's textures in 3D and a painted background in 2D? | Reads like the Arcane / Pinkman.TV reference on screen; strokes land where the agent meant them |
| Sound | Do sampled instruments + ACE-Step + recorded effects reach the reference soundtrack / effects? | Side by side, not obviously worse |
| 2D: Blitz vs Chromium | Does Blitz hold up on Apple-style reference frames (type, blur, gradients, masks)? | Partly done already (speed and fidelity passed); finish on the reference set |

---

## What happens to the current code

### Where it stands (2026-10-21, checked)

- **Nothing is running.** All three team branches (`team/hem`, `team/priyam`, `team/sam`) are fully merged into main; their worktrees have no unsaved work. The GUI run stopped at ~12:45 today (HANDOFF.md §3 lists its open items).
- **Main is 363 commits ahead of GitHub** (`samirx20/choreo`, last push 2026-10-20 evening).
- **Disk:** 98 GB free of 474 GB. Build folders: team-hem 8.3 GB, team-priyam 7.8 GB, team-sam 0.1 GB, main 4.3 GB; render cache (`C:\Users\Sam\.rostrum\cache`) 11 GB.
- **The GUI app** (one window, React in Tauri, ~290 files in `src/app`) exists and installs. Its Viewer gets each picture from a server as an image file, which is why playback reached only ~1–25 frames per second. That is evidence for the GUI shell proof: a web UI is only workable if the viewport is drawn natively or shared on the GPU, not sent as pictures.

### The switch-over — DONE 2026-10-21

- Main tagged **`experiment-final`** (commit `da3f2118`) and pushed with the tag to `samirx20/choreo`. GitHub now matches the laptop.
- The three team worktrees were removed (their `node_modules` links unhooked first, so main's own folder was untouched) and the branches `team/hem`, `team/priyam` and `team/sam` deleted. All were fully merged.
- Main's build folder went from 4.7 GB to 0.13 GB. The five finished engine programs were kept, because the Rostrum MCP tools that Claude sessions use still run from them. The render cache was emptied with `rostrum cache clear` (10.3 GB).
- Free disk went from **98 GB to 135 GB**.
- Left alone: the old `bugfix-session-wip` branch (from 2026-10-16, not part of this cleanup).

The steps as planned:

1. **Tag** main as `experiment-final` and **push** it with the tag to `samirx20/choreo`, so the whole experiment is backed up off the laptop.
2. **This repo becomes the read-only archive.** Its docs stay as reference: GUI_DESIGN, EDIT_MODEL, MARKERS, AI_MODELS, SOUND_LIBRARY, OSS_REUSE, TESTS, HANDOFF.
3. **Clean up:** remove the three team worktrees and their branches (all merged), main's build folder and the render cache — about 31 GB back. The tag keeps every line of code.
4. **New repository**, fresh history (the archive keeps the old history; the new README points to the `experiment-final` commit). Same team model: one permanent worktree per team.

### What carries over, part by part

| Part of the experiment | What happens | Goes to |
|---|---|---|
| Motion: DSL, registry, evaluator, edit model, stage renderers, export, Blitz + Skia renderer (`native/rostrum-motion`), motion MCP tools, craft guides | **Copied in** (renderer subject to the Blitz vs Chromium proof) | Rostrum2D |
| Sound: Rust engine (`native/rostrum-sound`), schedule, sound DSL, plugin hosting, Qwen3-TTS voice, Parakeet captions | **Copied in** | RostrumSound (captions → Editor) |
| Editor pieces: masks, stabilising, grading, captions, matchmove solver, compositor logic | **Ported to C++**, the old code as the reference | Rostrum Editor |
| 3D: Bevy engine (`native/rostrum-3d`, ~59k lines) | **Not carried** (archive only) | — |
| 3D TypeScript layer (`src/core/threeDsl`, `src/engine/three`, ~54k lines): generators built for the camera, materials, characters, simulations | **Ported to C++ / Python** where useful, as the reference | Rostrum3D |
| GUI app (`src/app`) | **The web-UI candidate** in the GUI shell proof. If web UI wins, its screens and kit carry over; if Qt wins, its design does (GUI_DESIGN.md), not its code | Shared GUI kit |
| Agent layer: MCP structure, edit history, markers, project format, cache, jobs queue | **Copied in** and generalized for four apps | Shared layer |
| Team tooling (`C:\Users\Sam\.rostrum\waves`: RULES, lead brief, quota probe, heartbeat) | **Kept**, updated for the new repo | Manager |
| Tests | Only those guarding carried code | With their code |

## Teams

Three teams — **Hem**, **Priyam**, **Sam** — each 3–4 members. Claude is the manager: writes the briefs, reviews, merges, judges results against the references with Sam. Sam judges pictures and sound.

**Rules that still bind:** one permanent worktree per team; at most **2 heavy teams at once** (16 GB, one 4 GB GPU); one heavy job per team (members never queue their own builds); small, time-boxed briefs; PROGRESS.md for takeover; work placed by quota (team Sam keeps a 25 % reserve for the manager); **shared-layer changes run alone and merge first**; Opus for engine / design work, Sonnet for features, Haiku for mechanical work.

### Stage 1 — Proofs (1–2 weeks)

| Team | Proofs | Heavy? |
|---|---|---|
| **Hem** | 3D: USD + Hydra + Cycles **product still**, then **painterly still**, then the **stylized Hydra plug-in** spike. Uses prebuilt libraries (vcpkg) where possible — building USD from source on this laptop takes hours | Heavy (C++ builds, GPU renders) |
| **Priyam** | **Sound** (sampled instruments + ACE-Step + recorded effects vs the reference), and **agent painting** in 2D first (strokes, seeing, grid) — the 3D part joins once Hem's still renders | Heavy (AI models on the GPU) |
| **Sam** | **GUI shell** (the current web app vs Qt, both holding a live native viewport and smooth video playback), finish **Blitz vs Chromium**, and the **new repo skeleton** with the shared-layer contract (project service, MCP conventions) | Light–medium |

### Stage 2 — Two tracks

| Team | Owns | Order of work |
|---|---|---|
| **Hem** — Track B | **Rostrum3D** | Base (scene, materials, lights, cameras, keyframes, Cycles, Python API, MCP) → **product / motion-design tools** (text and logos, glass and metal, product lighting, cloners) → painterly and stylized tools → characters and simulations. Members: C++ core / USD; rendering / Hydra; tools (modelling, materials, painting on models); Python API and agent look tools |
| **Sam** — Track A, shared layer | **Rostrum2D + the shared layer** | Shared layer first (project service, jobs queue, GUI kit, painting kit's brush engine) → Rostrum2D moved into the new repo on that layer (Draw, frame-by-frame, 2D characters, imports) → then leads the **Editor** (Story, Edit, Deliver). Owns the shared layer: other teams ask for changes, Sam's team makes them, merged first |
| **Priyam** — Track A | **RostrumSound**, then Editor pieces | Sound moved in (engine, samples, recording, MIDI and piano roll, mix, cleanup, agent "ears") → then the Editor's **Comp** and **Colour** pages (keyer, roto, tracking, grading) alongside Sam's team |

**Joins:** 3D product renders appear as live layers in 2D once Hem's base renders (late Stage 2). Painting: Sam's team builds the brush engine; Hem's team paints on models with it; Priyam's agent-painting tools from Stage 1 become part of the painting kit.

---

## Decided (2026-10-21)

- **Four apps:** Rostrum2D, RostrumSound, Rostrum3D, Rostrum Editor, plus a shared layer.
- **Rostrum3D in C++**, on USD + Hydra and the permissive film libraries. No Blender fork.
- **Licence: stay MIT** (current direction).
- **Platforms: Windows + Mac.**
- **Painting and drawing split across apps:** texture painting and sculpting in 3D; drawing and frame-by-frame animation in 2D. No fifth app.
- **AI models: local first, cloud optional** (users bring their own keys).
- **GUI shell: prove web UI and Qt, then pick.**
- **Build order: proofs first (1–2 weeks), then two tracks at once.**
  - **Track A:** Rostrum2D → RostrumSound → Rostrum Editor. The first complete pipeline: a finished motion-design video with its soundtrack. The shared UI kit is built alongside Rostrum2D.
  - **Track B:** Rostrum3D from day one, because it is the longest road. Order inside it: the base (scene, materials, lights, cameras, keyframes, Cycles) → **product and motion-design tools first** (logos and text, glass and metal, product lighting, cloners and effectors), which also give Track A its Apple-level product shots → then the painterly and stylized tools.
- **Code home: a new repository** with the four apps and the shared layer. What survives is copied in (2D, the sound engine, editor pieces, agent tools). This repo stays as the archive.
- **One installer**, pick which apps to install.
- **Firewheel: low risk.** The sound engine uses it in one file, only to send audio to the speakers; the rest is our own code. It can be swapped for `cpal` in a day if needed.
- **Editor pages:** Story → Edit → Comp → Colour → Sound → Deliver (Sam's §9 pages plus Story and Comp).
- **Opening between apps:** double-click a 2D / 3D / Sound item in the Editor and it opens in its own app at that moment; "back to edit" returns. This replaces the experiment's in-window dive-in.
- **Kept from the experiment:** one project with files hidden, the shared screen parts, Fast / Final, context layers, links between values, built for the camera, the dark clean look, agent changes as a reviewable group.
- **Sound:** stereo first; 5.1 and Dolby Atmos later.
- **Switch-over:** tag main `experiment-final`, push it to GitHub, then clean up the team worktrees, build folders and render cache (about 31 GB). This repo becomes the archive.
- **Teams:** Hem = Rostrum3D; Sam = shared layer + Rostrum2D, then leads the Editor; Priyam = RostrumSound, then the Editor's Comp and Colour pages. Proofs split the same way (see Teams).
- **Rostrum3D is scripted in Python**, the industry standard (USD, Maya, Houdini and Blender all use it). The current 3D TypeScript layer (~17k lines) is ported, not reused. Agents reach every app the same way through MCP.
- **3D tool sets: product / motion-design first, then the tools for painterly and stylized work** (see "Tools for painterly and stylized work"). We build tools, not a look or filter: people and agents make their own looks with them. Fortiche (Arcane) and Pinkman.TV (Alberto Mielgo), Sam's favourite styles, are the yardstick that proves the tools are good enough. Cel/anime and near-realistic work use the same tools. (Corrected 2026-10-21: Blur was picked by mistake.)
- **Agents paint for real.** New models paint well, so agents get proper painting tools — brushes, strokes, and the ability to see the canvas and know exactly where each stroke lands — not only "generate an image and project it".
- **Reference set: Claude drafts it, Sam edits** (below).

## Reference set (draft — Sam to edit)

References are for private comparison on Sam's machine only, never shipped or put in the repo. Each one is turned into a few concrete **moments to match**: a still frame (light, material, composition), a ~5-second move (timing, weight, camera), a sound cue.

**Rostrum3D — product shots** (first tool set): the same Apple launch films listed under Rostrum2D (product close-ups: glass, metal, light).

**Rostrum3D — painterly** (second tool set, Sam's favourite styles)
- *Fortiche:* Arcane (seasons 1 and 2); the League of Legends music videos "Get Jinxed", "Warriors", "POP/STARS", "Enemy"; "Ma Meilleure Ennemie".
- *Pinkman.TV (Alberto Mielgo):* "The Witness" and "Jibaro" (Love, Death & Robots); "The Windshield Wiper" (Oscar-winning short).
- *Later looks (secondary):* Spider-Man: Into the Spider-Verse (Sony Pictures Animation); Puss in Boots: The Last Wish (DreamWorks); Guilty Gear Strive trailers (Arc System Works, cel/anime).

**What their pipelines tell us** (from published interviews; tool names for reference only):
- *The Windshield Wiper:* Maya as the main tool, ZBrush for sculpting, Marvelous Designer for cloth, Photoshop / After Effects / Premiere for painting, compositing and editing. **All backgrounds painted by Mielgo**, keyframe animation, and **custom tools to shape each character's silhouette shot by shot**.
- *Arcane:* Maya, Houdini, Substance Painter, After Effects, and heavy hand painting.
- So Rostrum3D's painterly tool set needs: **texture painting**, **painted backgrounds** (2D Draw or painted cards in 3D), **per-shot silhouette shaping** (bend a character's shape for one camera only), **cloth**, **sculpting**, and a strong **Comp** page in the Editor (painted 2D effects, grain, colour).

**Rostrum2D**
- An Apple product launch film (an iPhone or MacBook Pro reveal): material close-ups, type, transitions.
- Apple keynote graphics segments: type and UI choreography.
- One launch film from another large tech company (Sam's pick).
- *Drawn/frame-by-frame:* Arcane's painted 2D effects and graffiti; Spider-Verse's hand-drawn effects.

**RostrumSound**
- *Soundtrack:* Arcane's score (Alexander Temple and Alex Seaver) and Fortiche's music videos (music-led cutting); Spider-Verse's score (Daniel Pemberton).
- *Sound effects:* the sound design of "Jibaro" and "The Witness"; the sound design of an Apple launch film (whooshes, clicks, material sounds).

**Rostrum Editor**
- The cutting and pacing of a Fortiche music video (cut to the music), "The Witness" (chase), and an Apple launch film.
- A 30-second vertical (9:16) social cut of one of them, for the versions-per-platform workflow.

## Later (deliberately not now)

Review and comments, cloud rendering, multicam, camera RAW formats, HDR delivery, 5.1 / Dolby Atmos, working together live on one project, UI in other languages.

## Still to decide

1. **Sam's edits to the reference set**, then pick the exact moments to match.
2. **How it is paid for** (not urgent): it stays MIT open source; options include selling ready-made builds and support (like Goo Engine), paid cloud rendering, or donations.
