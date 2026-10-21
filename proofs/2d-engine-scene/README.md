# Proof: the 2D engine evaluates the scene itself (Team Hem, H6)

**Question.** Can the Rust engine take the scene description (`apps/2d/ENGINE_CONTRACT.md` v1) and draw every
frame itself, exactly as the Python stopgap evaluator does, so the stopgap can be deleted?

**Verdict: pass.** Both test shots come out pixel for pixel the same from the Rust evaluator and the Python one
(all 90 frames of Meridian, all 180 of the P-2D shot). Working out a frame now takes 0.2 ms in Rust (0.5 ms in
Python); the rest of each frame is painting. One renderer issue was found on the way (below), and it is not in
the evaluator.

## Setup

- Engine: `apps/2d/engine` built with `--profile agent` (branch `team/hem`), GPU (RTX 3050, shared).
- The Python layer with the proposed handle change, `engine.py.patch` (applies to `apps/2d/python/rostrum2d/engine.py`
  at main `34993eb`), run from a scratch copy; Team Sam's folder was not edited.
- Shots, both through the scene description: Meridian (`C:\Users\Sam\.rostrum\waves\results\stage2\2d\agent\title.py`,
  S5) and P-2D's animated shot rewritten as a Rostrum2D script (`pro_shot.py`: same layout and timing; its
  conic-gradient ring, backdrop blur and soft-edged wipe have no scene equivalent yet and are approximated).
- `proof.py <patched rostrum2d parent> <scratch> <results>`: stills at four times and the whole video through each
  evaluator, scrubbing (frame after frame, then 60 random jumps, raw RGBA as the live canvas will ask), and 30
  one-layer drags (`edit` then the same frame again).

## Results (`C:\Users\Sam\.rostrum\waves\results\stage2\2d-engine\`)

- `meridian-python-vs-rust-evaluator.png`, `pro-shot-python-vs-rust-evaluator.png`: stopgap | engine | difference ×8,
  four moments each. The difference column is black (max difference 0).
- `meridian-engine-evaluator.mp4`, `pro-shot-engine-evaluator.mp4` (and the `-python-evaluator.mp4` pair).
- `*-rust-evaluator.png`: the engine's stills. `timings.json`: every number.
- Every frame checked as a still, both evaluators: 0 of 270 differ.

| Per frame, median (1920×1080) | Meridian (30 fps) | P-2D shot (60 fps) |
|---|---|---|
| evaluate + write the stage: Rust / Python | 0.18 / 0.46 ms | 0.19 / 0.57 ms |
| scrub forward, RGBA round trip, Rust | 35.6 ms (paint 31.5) | 39.1 ms (paint 34.4) |
| scrub, random jumps, Rust | 38.4 ms (worst 61) | 45.7 ms (worst 87) |
| one layer dragged (`edit` + frame) | 37.9 ms, 1 edit | 31.0 ms, 1 edit |
| export to H.264, Rust / Python | 40.4 / 46.0 ms | 35.1 / 39.0 ms |

The GPU was shared with other teams' work during the run; paint times move by ±30 % between runs.

**Open: a frame can depend on what the page drew before.** Meridian exported right after stills at 0.4–2.9 s
differs from a fresh export by 1–2 levels (of 255) in up to 222 of 2 million pixels, from frame 17 on. The stage
markup is the same, so it is a cache in the paint, most likely Skia's glyph cache on the GPU. It can't be seen, but
a frame should depend on its time alone (rule 5). This is why the two evaluators' videos measure 55–57 dB PSNR
apart instead of identical, while every still is identical.

Memory: one renderer process, as P-2D (about 220 MB); not measured again.
