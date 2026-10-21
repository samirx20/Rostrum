# Proof: 2D Design features through MCP only (Team Sam, S8, 2026-10-21)

**Question.** Can an agent make a short title at launch-film level through the `rostrum-2d` MCP server alone, using the
S8 features: a path drawn with the pen operations, text on a path, a frosted-glass card and a soft wipe?

**Verdict: pass with conditions.** Every step went through MCP: one script (`run_script`), the pen's own operations
(`path.add_point`, `path.set_point`, `path.fit` through `edit_document`), `look_frame` / `look_sheet` / `look_motion`, and
`render_video`. The title reads clean and the features all show. Conditions: it is a features piece, simpler than an
Apple launch film (the second half holds still), and the run found three bugs, all fixed (below).

## Setup

- `mcp_session.py` starts `python -m rostrum2d.mcp --project … --item launch` over stdio and sends a list of tool calls,
  waiting for jobs with `inspect_job`. `make_calls.py build` / `final` writes those lists; `film.py` is the script the
  agent ran.
- 1920 × 1080, 30 fps, 4 s. Engine: `apps/2d/engine/target/agent/rostrum2d-render.exe` built on this branch.

## Results (`C:\Users\Sam\.rostrum\waves\results\stage2\2d-design\`)

| File | What |
|---|---|
| `launch-title-4s.mp4` | the film (120 frames, H.264) |
| `launch-title-4s-contact-sheet.png` | every 10th frame of the mp4 |
| `frame-0.5-s.png`, `frame-1.2-s.png`, `frame-2.6-s.png`, `frame-3.6-s.png` | stills from the mp4 |
| `design-page-pen-path.png` | Design page, the pen-drawn path selected: points and handles on the canvas, stroke / dash / trim fields |
| `design-page-text-on-path.png` | the text on the path selected: Path and Letters groups |
| `design-page-frosted-card.png` | the glass card selected |
| `design-page-soft-wipe-mask.png` | the wipe mask selected: feather, invert, angle |

Timings were not measured on this run (each MCP batch, engine start included, finished within seconds).

## Bugs found by the run, fixed at the base

1. **A new path started as a 100 px square**, so the pen's first `path.add_point` extended that closed square.
   New paths now have no points; adding to a closed subpath starts a new one.
2. **`path.add_point` dropped an out handle without saying so** on the last point of an open path (path data stores it
   only once a point follows). It now refuses it loudly and says to set it with `path.set_point` after the next point.
3. **The engine handle mistook a progress line for the export's reply** when the keys came in another order
   (`{"of":…,"progress":…}`): `render_video` failed (loudly). The handle now reads each line as JSON.

## Also checked (S8 test renders; the type and path pictures are kept in `C:\Users\Sam\.rostrum\waves\results\S8\sam\`)

Tabular vs proportional figures, a stylistic set, slant + grade + XTRA, text on a curve, letters from the centre; a
star with gradient and outline shadow, rounded dashes, draw-on at half way, boolean subtract; conic disc, frosted card,
feathered + inverted mask, diagonal soft wipe, a video layer with a soft mask. Soft masks first came out hard: the
renderer draws no filters (blur) inside an SVG mask, and reads only what is inside the `<mask>` element; they are now
built from gradient pieces (`stage_fx.rs`).

## Attribution rows

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| skia-pathops | 0.9.2 | BSD-3-Clause (bundles Skia PathOps, BSD-3-Clause) | `apps/2d/python` (path booleans) | Python wheel | ships | Keep the notice | https://github.com/fonttools/skia-pathops |
