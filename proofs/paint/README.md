# P-PAINT · Agent painting (Team Priyam, brief P2)

**Question:** with **stroke**, **seeing** and **"where"** tools, can an agent paint a painted background in 2D and a prop's texture in 3D, reaching Arcane / Mielgo painted quality, with strokes landing where it meant?

**Verdict: pass with conditions.** The tools work: an agent can paint a full 1920×1080 background and repaint a 3D prop through the shot camera, see what it did at any zoom, and check where every stroke landed. Strokes landed where the agent meant them, to within about 1 pixel in 2D and 0–2 pixels on the 3D model; the few misses were surfaces seen almost edge-on, marks under 4 px, or the agent's own planning. **The quality does not reach Arcane / Mielgo yet.** The background went from a flat vector-like illustration (round 1) to a visibly painted one (round 2) once the tools were fast enough to look often, but the architecture is still boxes with painted skin and the far city is flat cut-outs. The repainted jug is cleaner and follows the form, but at frame size its strokes read as wheel-thrown streaks. The remaining gap is mostly painting time and judgement plus, in 3D, the stylized shading of P-3D-3, not placement. **Conditions:** the shared kit must keep a look under a second (cached pixels, a native brush engine) and add the tools listed at the end; judge the quality again on a longer painting session after that.

## What we built

All Python with numpy and Pillow (scipy in the 3D tools), started from Team Hem's P-3D-2 brush engine and its painters' wish list (`proofs/3d-painterly/README.md` › "What the painters needed"). Interface: `INTERFACE.md`.

### The 2D kit (`kit/`)

| File | What |
|---|---|
| `brush.py` | Brush engine: tips `round, bristle, chalk, flat` (Hem's) plus `block` (square-ended block-in) and `line` (crisp thin line); pressure sets width and opacity along a stroke; colour drift and **hue drift as its own setting**; wet blend and smudge (`wet`, optionally picking up the layers below); paper grain; modes normal / multiply / erase. Seeded, so every stroke replays exactly. |
| `doc.py` | The painting document. **The JSON list of operations is the truth**; pixels are rebuilt from it. Layers (normal / multiply / screen / add, opacity, visible, locked), named masks (polygon with feather, inverted, from a layer's alpha), strokes, fills, gradients, hatch block-in, **batches = one undo step** with a label and an author, undo / redo, history, snapshot after any batch, "which stroke last touched this pixel". |
| `see.py`, `where.py`, `paint.py` | The agent's CLI: `see` (any zoom, labelled pixel grid, one layer), `before-after` (last K batches with the changed box), `ref` (a reference beside the work at the same scale, optional difference), `values` (grey + value steps), `small` (as seen small), `what x y` (colour on every layer, top layer, top stroke and its batch, masks), `landed <stroke>` (miss in pixels), `history / undo / redo`, `run script.py`. |
| `HOWTO.md` | How an agent paints with the kit: the look loop, every command, a brush table. |
| `cache.py` | Round 2: the document's pixels, undo states and redo list cached next to it, keyed by a hash of the operations and the kit's own code; a mismatch replays and says so. |
| `test_doc.py`, `test_eyes.py` | 13 quick tests: replay and cache give identical pixels, undo / redo exact, old gradients replay the old way, locked layer fails loudly, `what` and `landed` right. |

### The 3D tools (`model/`), on Team Hem's still life

| File | What |
|---|---|
| `gbuffer.py` | A small software rasterizer of the P-3D-2 scene from the shot camera: per frame pixel the object, triangle, texture point (UV), position, normal, depth. 4.7 s at 1080p, 0.3 s cached. |
| `lookup.py` | **screen point → surface point → texture point** (`what X Y`) and back (`where MATERIAL TX TY`: every place that texel shows, visible or hidden and why). |
| `view.py` | "See it on the model": textures on the model through the camera, flat or lit (sun + cool fill), zoom with a frame-pixel grid, texel-size view; a work-in-progress texture via `--tex`. 2–5 s, no Cycles. |
| `project.py` | **Painting from the camera:** a screen-space paint layer (a kit document layer) is carried onto the texture, only where the camera sees that surface and it doesn't face edge-on; reports texels changed, paint that fell on other objects, edge-on drops; `--check` measures where paint landed. |
| `coverage.py` | Coverage map per texture: what the camera sees (coloured by on-screen size), what is painted, UV island edges. |
| `HOWTO.md` | How an agent paints a prop from the camera. |
| `check_align.py` | Measures our projection against a real Cycles render. |

`render/` renders the still life with a chosen texture folder through Hem's Cycles build (read-only use, under the gpu lock), reusing Hem's scene code unchanged.

## How an agent uses them

2D: write a stroke script (`with doc.batch("block in the sky"): doc.stroke("sky", curve(...), colour, 80, brush="block")`), run it with `paint.py <doc> run`, open the `see` picture, zoom where it matters, read colours and coordinates with `what`, check important strokes with `landed`, undo or change the script, repeat. Every step is a named batch in the history, with who made it.

3D: same kit document at frame size (1920×1080), painted over the shot; `project.py` carries each layer onto the texture; `view.py --mode lit --tex Jug=work.png` shows it on the model in seconds; `lookup.py` answers "what is at this frame pixel" and "where does this texel show"; `coverage.py` shows what still needs paint.

## Results (private, not in the repo)

All in `C:\Users\Sam\.rostrum\waves\results\stage1\p-paint\`:

| File | What |
|---|---|
| `brush-sheet.png` | every brush × even / taper / small / wet / smudge / grain, plus modes |
| `background-step1-blockin.png`, `background-step2-mid.png`, `background-step3-nearfinal.png` | round 1 in progress |
| `background-1080p.png` | round 1 final: our own canal at dusk, 1,555 strokes in 40 batches, ~75 min |
| `background-vs-reference.png` | round 1 beside an Arcane still (quality comparison only) |
| `background-round2-step1.png`, `background-round2-step2.png` | round 2 in progress (brushwork pass on the same document) |
| `background-round2-1080p.png` | **round 2 final**: ~6,480 strokes in all, 56 batches |
| `background-round2-vs-reference.png` | round 2 beside an Arcane still (quality comparison only) |
| `background-round1-vs-round2.png`, `background-round1-vs-round2-arch-crop.png` | round 1 above / left, round 2 below / right |
| `still-life-before-1080p.png` | P-3D-2 still life with Hem's jug, Cycles 256 samples, 39.6 s |
| `still-life-after-1080p.png` | the same with the jug repainted through the camera, 40.7 s, 1.03 GB video memory |
| `jug-before-after-crop.png` | the jug, before | after, cropped from the two renders |
| `jug-step1.png` … `jug-step3.png`, `jug-modelview-final.png`, `jug-modelview-final-frame.png` | jug rounds in the quick model view |
| `jug-coverage-final.png` | jug coverage after painting |
| `model\checker_cycles_vs_ours.png` | our projection over Cycles' labelled-checker render |
| `model\stroke_on_jug_lit_zoom.png`, `model\stroke_on_jug_check_overlay.png`, `model\stroke_on_pear2_check_overlay.png` | test strokes from the camera and where they landed |
| `model\coverage_jug.png`, `model\coverage_pear.png`, `model\texel_size_view.png`, `model\lit_view.png`, `model\where_pear_uv_0.5_0.4.png` | coverage, texel size, lit view, a "where" lookup |

Reference stills used for comparison (public press images, private): `C:\Users\Sam\.rostrum\references\paint\arcane-80lv-1.jpg`, `arcane-80lv-2.jpg` (from 80.lv's Arcane article).

## Do strokes land where the agent meant? Yes.

- **2D:** of the 16 strokes the two painters checked with `landed` (9 in round 1, 7 in round 2), none missed: mean error 0–1.1 px, worst 2.8 px (a stone wedge at the arch). All of the painters' mistakes were in planning (a radial gradient filling the whole layer, glows overwriting each other, shutters placed by guess, wet stones picking up the wrong colours), not placement; each cost an undo.
- **3D, alignment:** our camera projection matches Cycles' render of the labelled checker to within **0.02–0.13 px** (jug, bowl, pears, table, cloth); 3.8 px on the out-of-focus front pear, a weak match.
- **3D, strokes from the camera:** strokes 20 px and wider land within **0–2 frame px**, 85–100 % of each stroke showing.
- **The misses, and why:**
  - surfaces turned nearly edge-on to the camera (the lip flare, the bottom of the foot, the handle–body joint): paint thins or is dropped (cut-off 80°);
  - marks of 3 px or less: texture filtering blurs them (lip chips show 78–89 %);
  - one chip placed just off the jug's outline, onto the table: the painter's own error; the outline tool would have caught it;
  - shared textures: the three pears share one texture, so paint on one pear shows on another where they use the same texels. The tool reports it, but can't prevent it: that's a scene choice.

## Quality against Arcane / Mielgo (judged by eye)

**The background** (our own canal at dusk; `background-round1-vs-round2.png`, `background-round2-vs-reference.png`):
- Round 1 (75 min, 1,555 strokes): a sound design (one light, the bridge arch as the focus, clear value groups, believable depth) but it reads as a **clean vector illustration**: every plane one flat fill, hard ruler edges, no brushwork. The painter put this down mostly to the tools: each look took up to 67 s, so it leaned on quick fills instead of many observed strokes.
- Between rounds we fixed the base: the document keeps its pixels in a cache, so a look takes 3–4 s at 6,000 strokes instead of 67 s. Gradients now composite and fade, and there are glow modes (screen / add), an export command and a clearer `landed`.
- Round 2 (40 min, +4,920 strokes, same document): **clearly more painted.** The walls carry form-following brushwork with warm and cool colour and shutters, drainpipes and lit window detail. The light under the arch is now a broken field of painted ripples instead of a hard ellipse, and the arch stones are lit from below with the top lost in glow.
- **Still short of Arcane:** the buildings are boxes with a painted skin, where the reference paints the shape and material of every stone and wall section. Most outlines are still the hard round-1 shapes. The far city and the canal through the arch are flat cut-outs. Light is tinted onto surfaces, not shaped across them. Our judgement, and the painter's: the brushes can make the marks; what's missing is several times more careful, shape-by-shape painting time, which the remaining tool gaps (slow wet strokes, deep undo replays, no perspective guides) still discourage.

**The 3D jug** (`jug-before-after-crop.png`): the repaint is cleaner and follows the form: a sun side, a cool side, a curving light edge, warm light from the table, and a dragged cobalt rim (the most painted-looking part). But in the Cycles frame the strokes read as fine horizontal streaks, like a wheel-thrown pot, and the old jug's bigger, cruder patches actually read more "painted". Painting light into the colour also competes with the real light. Like P-3D-2 found, a painted 3D look needs the stylized shading of P-3D-3 (painted light edges, ramps, ink) as much as painted textures. The camera-painting tools are not what's holding it back.

## Times, memory, GPU

| | |
|---|---|
| Brush speed, 1920×1080 | ~37 dry strokes/s, ~9 wet strokes/s (CPU) |
| Opening a document by replay (round 1) | 3 s at the start, **67 s at 1,555 strokes**: the main slowdown in the look loop |
| Opening a document from its pixel cache (round 2) | **2–4 s** at 1,555–6,480 strokes; undo of one of the last 3 batches ~6–10 s; a deeper undo still replays (≈9 min once at 6,000 strokes) |
| Wet strokes picking up the whole picture | ~1.3 s each (260 wet drags took 3 min 21 s) |
| G-buffer / model view / lookup | 4.7 s first, 0.3 s cached / 2–5 s / 0.5 s |
| Projecting one paint layer onto a texture | 14 s on a quiet machine, 28–40 s under load |
| Cycles still, 1920×1080, 256 samples | 39.6 s before, 40.7 s after; RAM 2.3 GB; video memory ≤ 1.16 GB of 4 |

## What the shared painting kit (`shared/painting-kit/`) should take from this

Keep:
1. **The document as a list of operations**, batches as undo steps with labels and authors, exact replay, "which stroke touched this pixel". It worked for agents and fits `shared/core/OPERATIONS.md`.
2. **The seeing tools** (zoom with a labelled grid, before / after, values, small, reference side by side) and **the where tools** (`what`, `landed`), and in 3D the **G-buffer lookups both ways**, **painting from the camera**, the **quick model view** and the **coverage map**. Agents used all of them, and placement was never the problem.
3. **Frame pixels as the one coordinate for 3D painting**, with texels as a lookup.

Must fix or add (from the painters' notes, `background/NOTES.md`, `prop/NOTES.md`):
1. **Never replay to look.** Round 2 proved it: caching pixels by a hash of the operations cut a look from 67 s to 3 s, and the painting got visibly better. The shipped kit should go further: undo of any depth from stored states, and a Rust / GPU brush engine (wet strokes are ~1.3 s each in numpy) so a look takes well under a second.
2. **Image layers** (a locked underpaint or reference image layer that projection skips), and masks made from existing strokes (paint around the windows without repainting them). Compositing gradients and glow modes are done in this proof (round 2).
3. **Undo any batch, not only the last** (operations are independent where they touch different layers).
4. **Masks from the scene:** "mask from object / material" in 3D; perspective guides (vanishing points, a grid on a plane) in 2D.
5. **A per-stroke landing check on the model** (`prop/misses.py` is the prototype) and a `--check` that compares against the texture being painted and weighs soft paint.
6. **One stroke into several maps** (colour + roughness + height together), still open from P-3D-2.
7. **Faster projection** (GPU), so a 3D look round is seconds, not minutes.
8. **"Where are the lit things?"** queries over the document (by colour / value / layer), so an agent can find its own light sources without replaying its own random choices.

## Built, not tested

- `model/lookup.py --object`, `model/view.py --mode objects`.
- `kit/see.py` `ref` and `see --layer` were looked at on a stand-in document only in round 1 (the painter then used `ref` on the real one).

## Attribution rows

No new dependencies. numpy (BSD-3-Clause), Pillow (MIT-CMU), scipy (BSD-3-Clause), pytest (MIT, tests only) came from uv's cache and are already used by other proofs. Reference stills are private and not shipped.

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| NumPy | from uv cache | BSD-3-Clause | `proofs/paint` (brush engine, rasterizer) | Python package | dev only | Keep the notice | https://pypi.org/project/numpy/ |
| Pillow | from uv cache | MIT-CMU | `proofs/paint` (image files, masks) | Python package | dev only | Keep the notice | https://pypi.org/project/pillow/ |
| SciPy | from uv cache | BSD-3-Clause | `proofs/paint/model` (filters) | Python package | dev only | Keep the notice | https://pypi.org/project/scipy/ |
