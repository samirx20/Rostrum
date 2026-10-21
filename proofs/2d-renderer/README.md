# P-2D · Blitz vs Chromium (finish), and how Python drives the renderer

*Team Sam, brief S2, package C (member p2d), 2026-10-21. Time box 1.5 h.*

## The question

1. Does the experiment's 2D renderer (Blitz lays the page out, Skia paints it on the graphics card) hold up on the kind of frame a phone launch film has: big tight titles, heavy soft blur and frosted glass, rich gradients (also inside letters), masks and wipes, glow, depth?
2. How does a Python script layer drive it, and which work happens in Python vs in Rust?

Speed and fidelity on the experiment's own scenes passed earlier (2–7× faster than Chromium, mean SSIM 0.98–0.99; archive `docs/NATIVE_ENGINE.md` › Motion renderer). This proof only adds the launch-film quality bar and the Python question.

## Verdict: **pass with conditions**

Blur, frosted glass, glow, multi-stop and conic gradients, masks, wipes, text outlines and small text look the same as Chrome — and soft glows on dark backgrounds come out *smoother* than Chrome (no visible banding). Four things don't work yet, and launch-film titles need them, so they become Stage 2 work on our own copy of Blitz:

1. **Gradient-filled letters** (`background-clip: text`) are not supported: the whole box is painted instead of the letters. The SVG-text workaround fills the letters but loses our font and falls back to a serif.
2. **Automatic optical size** of variable fonts is missing. Chrome picks a display cut for big titles automatically; Blitz doesn't, so titles come out lighter and narrower than in Chrome. Turning that off in Chrome made the text match Blitz exactly.
3. **A parent's `perspective`** is ignored, so 3D-tilted cards render flat. `transform: perspective(…)` on each card does work.
4. **Blur on a 3D-tilted element** draws broken: the card is cut off, with a sharp inner rectangle.

Python can drive the renderer as it is today: Python works out the frame, Rust lays it out and paints it. A 3-second shot at 60 fps rendered to mp4 in about 10 seconds.

## Setup (exact commands)

Nothing was built or downloaded. Python standard library only.

- Renderer (read-only, from the experiment): `C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\native\target\release\rostrum-motion.exe` (`serve` mode: one JSON request per line on stdin, one JSON reply per line; archive `native/rostrum-motion/src/serve.rs`).
- Chromium: Google Chrome 155.0.8059.85, `C:\Program Files\Google\Chrome\Application\chrome.exe --headless=new --window-size=1920,1080 --force-device-scale-factor=1 --virtual-time-budget=3000 --screenshot=…`.
- Font: Roboto Flex (variable, SIL OFL) from `C:\Users\Sam\Documents\CODE\OLD-EXPERIMENT\public\fonts\variable\RobotoFlex.ttf`, embedded in each page as a data URL, so both renderers get the same font. The frames don't use SF Pro (not ours to ship).
- Graphics card: NVIDIA GeForce RTX 3050 Laptop GPU (the renderer picks it itself).

```
cd C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\proofs\2d-renderer\driver
set PY=C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\.venv\Scripts\python.exe
set SCRATCH=C:\Users\Sam\.rostrum\waves\scratch\sam-S2-p2d
set OUT=C:\Users\Sam\.rostrum\waves\results\stage1\p-2d
%PY% stills.py %SCRATCH% %OUT%                                      :: 4 frames + 3 workaround variants, both renderers
%PY% stills.py %SCRATCH% %OUT% type-alt,reveal-alt,depth-alt        :: only some frames
%PY% shot.py %SCRATCH% %OUT%\shot-python-driven.mp4 60              :: 3 s animated shot, Python-driven
%PY% parity_shot.py %SCRATCH% %OUT% 2.5                             :: one moment of the shot vs Chrome
```

Files (all in `C:\Users\Sam\.t3\worktrees\Rostrum\team-sam\proofs\2d-renderer\driver\`):
- `rostrum2d.py`: the Python handle on the renderer (start, open a page, render a still, send frames to ffmpeg, finish, peak memory, always ends its own process).
- `frames.py`: the four frames (our own designs) plus the three workaround variants.
- `stills.py`: renders each frame with both renderers and makes the side-by-side, the difference picture and the SSIM score.
- `shot.py`: the animated shot (layers, keyframes, easing evaluated in Python).
- `parity_shot.py`: one moment of the shot, both renderers.

## Results

All in `C:\Users\Sam\.rostrum\waves\results\stage1\p-2d\`. For each frame: `<name>-blitz.png`, `<name>-chromium.png`, `<name>-blitz-vs-chromium.png` (Rostrum on the left, Chrome on the right) and `<name>-diff.png` (the difference, made 4× brighter).

| Frame | What it tests | SSIM | What I saw |
|---|---|---|---|
| `type` | Big metallic gradient title, wide-tracked eyebrow, light subtitle, small body text, blurred warm glow | 0.81 | **Fails on the title:** `background-clip: text` is ignored, so a metallic bar covers the title's box. The glow, rule line and small text match. The subtitle is a little wider in Blitz (optical size, see below). |
| `type-alt` | Same title as an inline SVG `<text>` with a gradient fill | 0.89 | The gradient fill works, but the SVG text can't find our web font: it falls back to a serif. Chrome draws it correctly. |
| `glass` | Blurred colour orbs, frosted-glass card (`backdrop-filter: blur + saturate`), glass pill, thin gradient numerals | 0.96 | **Glass, blur, inset highlight and shadow match very well.** The only failure is the gradient-filled "48" (same gap: it draws as a gradient box). |
| `reveal` | Conic-gradient ring cut by a radial mask, blurred glow copy, giant gradient "Pro" faded by a mask, clip-path wipe, outlined text | 0.73 | The ring, its glow, the mask fade and the wipe match. "Pro" is a gradient box again. **The outlined text is missing**, because Blitz reads `-webkit-text-stroke` only from a `style=""` attribute, not from a stylesheet. |
| `reveal-alt` | Same, with SVG gradient text and the outline as an inline style | 0.93 | The outline now matches Chrome. SVG "Pro" has the gradient but in the fallback serif. |
| `depth` | Three tilted phone-like slabs with a parent `perspective`, depth blur on the far ones, a screen-blended highlight, glowing title (`text-shadow`), floor, vignette | 0.92 | **Glow title, highlight, floor and vignette match.** The slabs are flat: a parent's `perspective` is ignored. |
| `depth-alt` | Same, with `transform: perspective(…) rotateY(…)` on each slab | 0.95 | The sharp front slab now tilts exactly as in Chrome. **The two blurred slabs are broken**: one is cut to a sliver, the other shows a sharp inner rectangle. Paint time also rose to 162 ms for this frame. |
| `shot-0.4s`, `shot-2.5s` | Two moments of the animated shot (`shot-…-blitz-vs-chromium.png`) | 0.99, 0.96 | Match. The only visible difference is the title's optical size: Chrome's "Pro" is the heavier, wider display cut. |

Other results:
- `shot-python-driven.mp4`: 3 s, 60 fps, 1920×1080, H.264 (180 frames, checked with ffprobe). Blurred orbs drift, a conic ring turns and scales in, "Pro" rises with its weight going 200 → 860 and its tracking going wide → tight, revealed by a moving mask, with a growing glow, and a frosted-glass "BEYOND PRO" card slides up.
- `shot-python-driven-contact.png`: 4 frames of the shot.
- `shot-timing.json`: per-frame timings from the renderer.

**Optical size check:** I rendered `type` in Chrome again with `font-optical-sizing: none`. The subtitle and body text then line up with Blitz letter for letter (I looked at a 1:1 crop; it was in my scratch folder, which is now deleted). So the width difference is Chrome's automatic optical size, not Blitz's text shaping. Not tested yet: whether Blitz honours an explicit `font-variation-settings: "opsz" N`. If it does, the fix lives in our layer: Python writes the optical size from the font size.

**Banding:** In a 6× brightened crop of the warm glow, Chrome shows visible steps and Blitz is smooth. The renderer paints in 16-bit float and adds dither when it writes 8-bit. This is one reason the Blitz PNGs are larger.

**Font rendering:** Small text (19–20 px) is clean in both. Blitz uses greyscale smoothing, which is right for video. Chrome's headless screenshot shows colour fringing.

## Timings (RTX 3050 laptop, 1920×1080)

Single stills, measured on the second paint of each frame (median of one; first paints add fonts and shader setup):

| Frame | Rostrum round trip (paint + PNG write) | of which paint | Chrome screenshot (with browser start) |
|---|---|---|---|
| type | 36 ms | 20 ms | 1.3 s |
| glass | 48 ms | 26 ms | 1.3 s |
| reveal | 64 ms | 44 ms | 1.1 s |
| depth | 110 ms | 73 ms | 1.4 s |
| depth-alt (3D + blur) | 198 ms | 162 ms | 1.4 s |

(Chrome's time is mostly browser start-up, so it isn't a per-frame speed comparison. The archive's earlier speed proof did that properly: 2–7×.)

Animated shot, 180 frames at 60 fps, rendered straight into ffmpeg (`shot.py`, second run):
- Whole render including encoding: **10.2 s** for 3 s of video (about 18 frames rendered per second). The first run took 8.1 s; the laptop's GPU is shared.
- Median per frame: **Python evaluates the keyframes and writes the markup in 0.5 ms**; the renderer finds the changes (diff) in 0.36 ms, lays out in 0.73 ms, paints in 19 ms (12 ms recording the scene for Skia); waits 8.6 ms for the encoder. Round trip 44 ms, worst frame 180 ms, first frame 77 ms. Opening the page took 109 ms. Finishing ffmpeg took 1.3 s.
- Most of each frame is painting five large blurs (80 px orbs and the ring glow) at full 1080p. Python's share is about 1 %.

## Memory

- Renderer process peak working set during the shot: **221 MB** (read with `GetProcessMemoryInfo`).
- Graphics card memory: not measured per process. Before the runs the card showed 10 MB used, and nothing else was running on it.
- The Python driver itself is tiny: it holds the markup strings only.

## What Python does vs what Rust does

**Today (this proof):**
- **Python:** holds the document (layers, their styles, keyframes) and, **every frame**, evaluates each animated property (easing, interpolation) and writes the whole stage as HTML markup with inline styles. It also starts the renderer and tells it where to send frames (ffmpeg).
- **Rust (`rostrum-motion serve`):** parses that markup into a scratch page, diffs it against the page it keeps (here 7 edits a frame), restyles (Stylo), lays out (Taffy + Parley), paints (Skia on the GPU), reads the pixels back, and pipes them into ffmpeg itself, so pixels never pass through Python.

This is the same split the experiment had, with TypeScript in Python's place. It is the smallest honest route, because the exe only takes per-frame markup.

**Target design:** Python describes the document and its animation **once**; Rust evaluates per frame.
- Python sends the scene (layers, styles, keyframe tracks, easing curves, markers) as one structured document, and after that only the operations an agent or person makes (add a key, move a layer). Those are the same operations recorded in the one history (AGENTS.md rules 3–4).
- Rust holds the document, evaluates every track at time *t*, and applies the changed values straight to its kept page as style edits. No markup is written, parsed or diffed per frame. It renders frames, ranges, storyboards and exports from that one path (rule 5).
- Interface: start with the **long-lived process protocol** that already works (JSON lines, as here), with new requests: `load document`, `apply operations`, `render frame t` / `render range a–b to encoder`, `look` (boxes, stats). Add a **PyO3 module** (`import rostrum2d_engine`) later, if needed, for in-process calls and zero-copy frames in the GUI. The process protocol keeps a crash in the renderer from taking down the GUI or the MCP server, and it is what the MCP tools would call anyway.
- Gain: the per-frame markup and diff are small now (about 1 ms), but they grow with layer count and particle data. The bigger win is one evaluator that the GUI preview, scripts and export all share, instead of re-creating it in every language.

## What we would have to maintain ourselves (Blitz is officially pre-alpha)

From the archive's `native/Cargo.toml`, `native/Cargo.lock` and `native/rostrum-motion/vendor/PATCHES.md`:

1. **Exact pinned versions:** `blitz-dom` / `blitz-html` / `blitz-paint` / `blitz-traits` `=0.3.0-beta.3`, `stylo =0.22.0`, `anyrender 0.14.0`, `anyrender_skia 0.12.0`, `parley 0.12.0`, `usvg 0.48.1`, `skrifa =0.44.0`, `skia-safe 0.153.3` (with its prebuilt Skia binaries), `taffy 0.10.1` (two taffy versions are in the lock: 0.10.1 and 0.15.0). There are 810 packages in the experiment's lock file (shared with the sound and 3D engines). No git revisions: everything comes from crates.io and is pinned.
2. **Six vendored, patched crates** (our own copies, swapped in with `[patch.crates-io]`): anyrender (14 files), anyrender_skia (15), blitz-dom (59), blitz-paint (27), parley (47), usvg (40), about 77k lines. **About 40 patches over 13+ rounds**, among them: SVG filters (the whole grade, key and effect graph), 3D transforms as 4×4 matrices, mix-blend-mode, backdrop-filter layering, text-shadow, text outline, inline-span margins and padding, split-text line breaking, table baselines (KaTeX), the measure-cache baseline fix that allows incremental layout, runtime shaders (SkSL), LUT and matte children, raster warps and meshes, particles, motion-blur sum, soft clip edges, an image registry with a memory cap, comp-cache taps, raw RGBA pictures. Each upstream release means rebasing all of them. None has been sent upstream yet.
3. **Stylo built for Servo** does not parse several CSS properties we use (`-webkit-text-stroke`, `paint-order`, `url()` filters). The patches read them from the inline `style` attribute instead. That's why a text outline in a stylesheet silently vanished in this proof. Our layer must always write these inline, or we patch Stylo's property list, which is a fork of a large Mozilla/Servo crate.
4. **Gaps found in this proof** (new work): `background-clip: text`; automatic `font-optical-sizing`; web fonts with variable axes inside SVG `<text>` (it falls back to a serif); parent `perspective` / `transform-style: preserve-3d`; `filter: blur` on a 3D-transformed element.
5. **Known open from the archive:** opacity and filter layers clip to the element's box in some cases (an upstream TODO, partly patched); Blitz's own incremental layout bug was patched by us (round 9), not upstream.
6. **Skia / skia-safe upgrades:** skia-safe changes API between versions, and anyrender_skia plus our patches call it directly (image filters, runtime effects, `draw_vertices`). Any skia-safe bump means touching our patched anyrender_skia.
7. **Platform:** the renderer opens OpenGL through a hidden window (glutin, `windows-sys`) and exports the hybrid-GPU hints. Mac needs its own GL/Metal path checked (Skia supports Metal, but the experiment's painter is GL only).

**Advice for Stage 2:** treat Blitz, Stylo-for-Servo, anyrender and parley as **our fork** with a named owner. Keep `PATCHES.md`. Add a scene test for every CSS feature agents rely on, so missing support fails loudly instead of drawing something else. Upstream the general patches (3D transforms, blend modes, text-shadow, inline padding) to shrink the fork.

## Open issues

- The four gaps in the verdict (gradient text, optical size, parent perspective, blur under 3D) need patches in our Blitz copy. That needs a cargo build, which this brief didn't allow.
- Untested: an explicit `font-variation-settings: "opsz"` in Blitz; a Mac run.
- A blur on a 3D-tilted element paints slowly (162 ms) as well as wrongly.
- Not a renderer issue: three idle `rostrum-motion.exe serve` processes (PIDs 11372, 15080, 17940) have been running since 13:59 today. The experiment's MCP servers (`node …\OLD-EXPERIMENT\dist\mcp.js`) keep them warm. They aren't this proof's, so I left them running.
