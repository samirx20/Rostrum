# P-PAINT, 3D half: repainting the jug through the shot camera

Member **prop**, Team Priyam, brief P2. Opus, medium effort. Worked 16:46–17:20 (about 35 of the 65 minutes).

**Question:** can an agent repaint a prop's texture by painting over the shot, and do the strokes land where it meant them to?
**Answer: yes for placement, and only partly for quality.** Strokes of 20 px and up land on the model within 0–2 frame pixels of where they were painted, with 85–100 % of their painted area showing. Marks under about 4 px are where it breaks down (see the misses table). The jug no longer looks blotchy. It now reads as cream enamel, with a warm side facing the sun, a cool side turned away, and a dipped cobalt rim and foot. It does not reach Arcane / Mielgo level (see the judgement at the end).

## Files

| File | What |
|---|---|
| `01_blockin.py` | enamel layer: ground fill, rings of warm / mid / cool strokes, the sun plane, the table's warm bounce, handle ground |
| `02_cobalt.py` | cobalt layer: rim band, its dipped and dragged lower edge, foot band, handle stripe |
| `03_accents.py` | accents layer: big form strokes, bounce, worn lip line, chips (iron dabs inside a pale cracked ring) |
| `04_edges.py` | edges layer: the light / shadow edge broken into warm and cool dabs, a wider bounce |
| `_geo.py` | placement helpers in frame px: `edges(y)`, `ring(y, t0, t1)` (a stroke path that wraps the jug, bowing down as the camera looks down), `along_edge(...)`, `light_edge(y)`, the handle centre line |
| `silhouette.py` → `silhouette.json` | the jug's and handle's outlines in frame px, read from the model's G-buffer. They become the kit masks `jug` and `handle` |
| `jug.paint.json` | the kit document (1920×1080). It replays its own stroke record |
| `build.py` | rebuilds everything: `uv run --with numpy --with pillow --with scipy python -I build.py --scripts [--check DIR] [--view OUT.png]` |
| `misses.py` | stroke-by-stroke landing check (below) |
| `textures/jug.png`, `jug_height.png`, `jug_rough.png` | the final set, to replace Hem's three |

`build.py --scripts` replays the four scripts into a fresh `jug.paint.json`. It then projects the four paint layers in order (`project.py`, objects Jug + JugHandle), starting from Hem's `jug.png`. Last it writes the height map and copies the roughness map. On a quiet machine this takes about 2 minutes; under load from other agents it took 5. Texels the camera doesn't see keep Hem's paint: `coverage.py` shows 908,034 texels painted against 906,428 seen. The 2,791 "painted but unseen" texels are the 2-texel seam growth.

**Height map (my call):** `build.py height()` is a high-pass at radius 2 texels (Hem used 6), gain 1.0 (Hem used 1.5), then a 1-texel blur. Over the seen area its spread is 0.016 against Hem's 0.054, so the relief is about 3× gentler, and it only picks up stroke-scale edges, not blotches. Enamel is a glaze, and the plaster look came from that wide, strong relief. **Not seen in Cycles yet:** the model views have no bump, so the lead's render is the only test of this.
**Roughness:** Hem's map is kept unchanged (glossy, mean 0.22 plus clear coat). The new paint didn't call for a change.

## Steps

| Step | Strokes | Time | What I saw (model view, lit) |
|---|---|---|---|
| 1. Block-in + cobalt (`jug-step1.png`) | 91 enamel + 29 cobalt | ~6 min | The planes landed exactly. But the warm / mid / cool split read as three straight vertical stripes, and the cool side was too blue: the view's own shading darkens it again. The scalloped rim edge read as a cartoon zig-zag. |
| 2. Accents + chips (`jug-step2.png`) | +37 | ~8 min | The chips read as black dots or flies on the body. The thin bristle accents didn't show at all. |
| 3. Light edge follows the form; chips only on edges; looser rim edge (`jug-step3.png`) | 118 + 42 + 48 | ~8 min | The light edge now curves: the shoulder holds the light, the belly gives it up toward the table. The chips sit on the lip and foot as small torn marks. |
| 4. Broken edge + wider bounce (`jug-modelview-final.png`) | +47 = **255 strokes** | ~6 min | The edge between light and shadow is now dabbed rather than clean. The warm bounce shows along the lower right. |

Each round was: edit the script, `build.py --scripts --check --view`, look at the zoomed lit view, and look at the check overlay for each layer.

## Misses table

From `misses.py`, final document. Each listed stroke is projected alone in a code colour onto a grey jug; the flat model view is rendered, and each code colour is found again in the frame. "Offset" = centre of where it landed minus centre of where it was painted, in frame px.

| Stroke | What | Painted at (frame px) | Offset (px) | Reach | Why |
|---|---|---|---|---|---|
| 30 | enamel ring (mid plane) | 578, 268 | −0.8, +1.8 | 99 % | clean |
| 60 | enamel ring | 535, 493 | 0.0, 0.0 | 98 % | clean |
| 120 | cobalt rim ring | 622, 14 | −0.1, −0.1 | 97 % | the lip flare, close to edge-on, drops a few px |
| 152 | foot band ring | 478, 668 | +0.2, +0.1 | 99 % | clean |
| 160 | handle stripe (7 px line) | 257, 309 | +12, +4* | 100 % | lands fully. In an earlier run the end inside the handle–body joint got no paint (centre −6 px): the joint is hidden or edge-on |
| 161 | form stroke from the left edge | 481, 258 | −7.5, −0.6 | 89 % | the stroke's thin tapered tail (low pressure) gets blended away by texture filtering. Its start at the silhouette is edge-on |
| 164 | form stroke | 443, 462 | −1.6, −0.3 | 97 % | as 161, smaller |
| 212, 230 | broken-edge dabs (~15 px) | 606, 171 / 629, 418 | −0.2, +0.1 / +0.1, −9.7* | 97 / 100 % | clean |
| 177, 185, 189 | lip chips, iron dabs 4–6 px | 424,17 / 607,28 / 694,20 | ≤ 0.4 | 78–89 % | the lip is close to edge-on and these marks are only 2–3 texels wide: their edges blur |
| 196 | foot chip | 522, 704 | +0.2, 0.0 | 96 % | clean |
| 193 | lip chip, 3 px | 730, 12 | −6.9, +1.6* | 100 % | tiny mark at the right end of the lip |
| 199 | foot chip | 688, 698 | — | 0 % | **real miss:** I placed it 1–3 px below the foot's outline, on the table. My mistake; `silhouette.json` would have told me |
| 203 | foot chip, 3 px dab | 590, 709 | — | 0 % | **lost:** 3 px at the very bottom edge of the foot, which is edge-on there |
| 207 | handle-end chip | 359, 149 | — | 0 %* | it shows in the lit view. The measurement failed here (see *) |

\* **Not trustworthy:** `misses.py` gives each frame pixel to the nearest of 21 code colours. Where two of them blend, a pixel can look like a third, which produces a few stray pixels far away (the "farthest stray" in the raw output). That inflates the offset for small strokes. Strokes with no strays (most of the rows above) are exact. Fix: run fewer strokes per run, or use well-separated colours. I didn't get to that within the time box.

**In short:** at this shot's density (about 1.9 texels per frame pixel), placement is not the problem. Misses come from (1) edge-on surfaces: the lip flare, the bottom of the foot, the silhouette, the handle–body joint; (2) marks of 3 px or less, which texture filtering blurs into their surroundings; and (3) my own placement off the outline. The handle shares `jug.png` but has its own island, so painting it never leaked onto the body: `changed_px_on_other_objects` is empty for every layer.

## Tool problems and gaps

1. **`project.py --check` compares against the texture in `paint/textures`, not against `--tex`.** When layers are chained, every later layer's check counts the earlier layers' changes as misses (my first cobalt check said mean 101 px, max 290 px). Workaround in `build.py`: check each layer alone against Hem's texture. Fix: compare against `--tex`.
2. **The `--check` miss figure counts paint as "intended" only above 50 % opacity.** Soft strokes, tapered tails, glazes (the 0.5-opacity bounce) and thin bristle hairs all show as magenta "changed where you didn't paint", even though they landed (accents layer: mean 3 px, max 61 px, all of it from this). It needs a softer test, for example opacity-weighted, or "changed within N px of any paint".
3. **No per-stroke landing check on the model.** The kit's `landed <id>` only checks the 2D canvas. I wrote `misses.py` for this. It belongs in `model/` beside `project.py`, with the colour-collision issue fixed.
4. **No underpaint layer.** The kit Doc can't hold an image layer, so I couldn't put the model view under my strokes as a locked guide. I worked from zoomed model views with the grid plus `silhouette.json` instead. A `doc.add_image_layer(name, png, locked=True)` that projection skips would make painting much easier.
5. **No object outline masks.** The kit has no "mask from object" (Jug, JugHandle). `silhouette.py` makes polygon masks from the G-buffer. This should be a `lookup.py mask <object>` command.
6. **The lit view's sun has a hard-edged terminator** (Lambert, no soft light), and it competes with painted light planes. The lit view isn't Cycles, so judging "light painted into the colour vs the real light" needs a Cycles look round, and members can't run one. I couldn't judge the double shading (painted shadow plus rendered shadow) properly.
7. **Speed:** one projection of one layer takes 14 s on a quiet machine and 28–40 s under load. Five layers plus checks means 2–5 minutes per look round, which slows the loop more than anything else.

## Judgement against the bar (Arcane; Mielgo's The Witness / Jibaro)

Better than Hem's jug:
- The form reads as painted planes: a sun side, a curving light edge (shoulder lit, belly turning away), a cool side, and warm light bounced up from the table.
- The blotchy lavender patches are gone. The chips sit on the lip and foot, where knocks happen.
- The relief map is about 3× gentler, so the jug should no longer read as plaster (to be confirmed in Cycles).

Still short of the bar:
- At frame size the strokes melt into fine horizontal streaks, like a wheel-thrown pot rather than a painting. Mielgo's props read as a handful of big, confident shapes with hard and soft edges chosen on purpose. Mine are many medium strokes with even edges.
- Painting light into the colour texture fights the real light. In Cycles the shadow side may come out darker and bluer than I intended (painted cool plus rendered shadow). The real fix is the stylized shading of P-3D-3 (painted light edges in the shader), not more paint in the colour.
- The cobalt rim is close: its dragged, dripping lower edge is the most "painted" part. The foot band is too even.

**Verdict for the 3D half of P-PAINT:** the tool chain works. An agent can paint in frame pixels, see the result on the model in seconds, and measure where strokes landed. Placement is accurate to about 1 px for strokes of 20 px and up. For quality, the bottleneck is now painting judgement and the shading model, not placement.
