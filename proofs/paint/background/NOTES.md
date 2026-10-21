# P-PAINT background: a canal at dusk (member painter, Team Priyam P2)

**The painting:** `canal.paint.json` (40 batches, 1,555 paint ops / stroke ids). Final picture:
`C:\Users\Sam\.rostrum\waves\results\stage1\p-paint\background-1080p.png` (1920×1080).
Steps: `background-step1-blockin.png`, `background-step2-mid.png`, `background-step3-nearfinal.png` (1600 wide),
and `background-vs-reference.png` (beside `arcane-80lv-2.jpg`), all in the same folder.

**What it shows:** looking down a narrow city canal just after sunset. Tall plaster houses on both banks in cool
shadow, a scattering of lit windows, a lamp post on the left quay, a moored boat with a lit cabin on the right, a
washing line across the canal. At the far end a stone bridge; through its arch the canal goes on into a glowing
haze, with the far city as silhouettes above the bridge. One light: the warm glow left behind by the sun, beyond the
bridge; the lamps and windows are small warm accents. The water mirrors the arch's glow, broken into ripples.

**How:** 7 stroke scripts, all through the kit (`doc.stroke`, `fill`, `gradient`, `fill_region`, masks):
`01_blockin` (layers, polygon masks, flat values) · `02_sky` · `03_walls` (8 building masks, tone, texture hatching,
81 windows as `block` strokes in perspective, sills, cornices) · `04_water` (mirrored bridge and arch, 167 glow ripples,
443 window-reflection dashes, 260 sky ripples) · `05_far_bridge_sky` (far city haze, canal seen through the arch,
voussoirs, parapet and railing, bridge lamps) · `06_clouds_near_light` (cloud banks, pipes, quay lip, bollards,
washing line, lamp post, boat) · `07_light_air` (warm/cool bristle pass on walls, damp stains, glows, vignette).
`_geo.py` holds the vanishing point and wall-plane formulas; `_windows.py` replays 03's random draws with a do-nothing
doc so later scripts know exactly where the lit windows are (checked with `what 1797 420`: it hits window stroke 66).

**Note:** the last two batches of `06_clouds_near_light.py` ("light", "vignette") were undone and replaced by
`07_light_air.py`, and the first versions of 04 and of the clouds in 05 were undone too. So running the scripts
01→07 again does **not** rebuild this document; the `.paint.json` is the truth.

Time: about 75 min in all. Stroke count: 1,555 stroke ids. About 1,300 are single strokes; the 30 `fill_region` ops
each hide dozens to hundreds of hatch strokes.

## Did the strokes land? (`landed`)

| Stroke | id | Result | Note |
|---|---|---|---|
| lit window (block) | 66 | landed, mean 0.12 px | |
| first voussoir (block, 26 px) | 1178 | **"landed", but max 2.81 px is over its own 2.6 px miss limit** | The verdict seems to go by the mean, while the printed limit reads as if it applied to the max. Confusing; see gaps. |
| arch lip (flat, 4 px) | 1224 | landed, 91 % of the path got paint | `flat` fades its ends on purpose, so about 9 % reads as "no paint". Not a miss. |
| parapet rim (flat) | 1225 | landed, 92 % | same ragged-end effect |
| quay lip (mask `!water`) | 1496 | landed, 88 % | ragged ends again; 0 % outside the mask |
| washing line (line, 2 px, 1,509 px long) | 1501 | landed, mean 0.00 | |
| lamp glass | 1509 | landed | |
| boat gunwale | 1513 | landed, 92 % | |
| lamp glow dab (round, 320 px) | 1548 | landed | |

No real misses. Every mistake I made was in **planning**, not in placement:
- **Sky glow covered the whole sky** (block-in): a radial `gradient` fills the whole layer and clamps to its outer
  colour, so a "hot spot" turned the entire sky orange. Fixed by painting over it, with the glow on its own screen layer.
- **Glows wiped each other** (06 "light"): 30 radial gradients on one screen layer; each one replaced the layer, so
  only the last survived. `before-after` showed it at once. Undone, redone as soft `round` dabs (hardness 0).
- **Bridge reflection had a hard rectangle edge** (04): my mask was too wide and unfeathered. Seen in `see`, undone
  (5 batches), redone with a feathered mask.
- **Clouds as even, same-sized dashes** (05): looked like a pattern, not clouds. Undone, redone as clustered banks.

## Tool problems: the requirements list

1. **Every command replays the whole document.** `Doc.open` reruns every op from the JSON. Each `see`, `what`,
   `landed`, `undo` and `run` paid the full replay: 3 s at the block-in, **67 s at the end** (1,555 ops). Painting
   time: running 05 took 2 min 34 s, mostly replay plus the chalk `fill_region` on the bridge. That cost decided how
   few looks I took near the end: I zoomed less than I should have. **Needed:** a pixel cache saved next to the JSON
   (keyed on the batch list), or a running session (REPL / MCP server) that keeps the document open. I worked around
   it by writing one Python script that opens the document once and runs all the `landed` checks, the export, `values`,
   `small` and `ref` in that one process.
2. **`gradient` always covers the whole layer**, outside the mask or not. There is no "fade to transparent" and no
   "add / screen" paint mode, so glows, haze and light pools can't stack on one layer. **Needed:** radial gradients
   that fade to alpha 0, and `screen` / `add` as paint modes (today only normal / multiply / erase).
3. **No export command.** `Doc.export_png` exists but the CLI doesn't offer it. I used `see --size 1920 --grid 0`
   (it gives exactly 1920×1080) and later `export_png` from my own script. **Needed:** `paint.py doc export out.png`.
4. **`landed` verdict vs. its printed limit** (stroke 1178 above): it prints "a miss is more than 2.6 px" next to
   "max 2.81 px" and still says "landed". Say which number the verdict uses.
5. **`landed` counts the designed ragged ends of `flat` as "no paint"** (88–92 % on clean strokes). Fine once you
   know; it would read better if the brush's own end fade were left out.
6. **Ops outside a batch become one batch each.** `add_layer` and `mask_polygon` before my first `with doc.batch`
   made 14 tiny batches ("add_layer", "mask"), which clutter `history` and make undo by batch fiddly. Group them, or
   let scripts open one batch that holds setup.
7. **Undo is only "the last batch".** Fixing the water meant undoing 5 batches and repainting all of them. **Needed:**
   undo of a named batch in the middle (replay without it), or hide / show a batch.
8. **`_look/` pictures are written inside the worktree** (next to the document), so they would end up in commits.
   They belong in a temp or scratch folder, or the folder should be git-ignored.
9. **No perspective help.** Windows, sills and cornices on receding walls needed my own vanishing-point maths
   (`_geo.py`). A "plane" helper (four corners → map (u, v) to canvas) would make architecture much easier for agents.
10. **No stroke-level colour variety inside one `fill_region`** apart from `color_jitter` / `hue_jitter`: real wall
    plaster needs patches of different colours. I layered several regions to get it. A colour list or a source
    image to sample from would help.
11. **No way to ask where the lit things are**: I had to replay my own script's random draws (`_windows.py`). A
    query like "strokes in batch X with their paths" (`doc.stroke_info` exists, but only by id) would do it.
12. **Speed of soft dabs is fine** (a 1,000 px round dab cost nothing noticeable); the slow parts were replay and
    big `chalk` / `bristle` hatches.

The seeing tools did not mislead me. `before-after` and `what` were the most useful. `values` confirmed the plan
(74 % dark / 21 % mid / 5 % light, with the light shapes exactly the arch, its reflection and the sky glow).

## Honest judgement against the reference

**What reaches it:** the design. One clear light, a strong focal point (the arch and its mirrored glow make a ring of
light the eye goes to), good value grouping (`values` / `small` read at thumbnail size), believable perspective,
aerial haze in the distance, a story in the place (washing line, moored boat, lamp).

**What doesn't:** the surface. Side by side with the Arcane still, mine reads as a **clean vector illustration**, not a
finished matte painting. Arcane's frames have:
- **visible, varied brushwork everywhere:** patches of colour inside every plane, dabs that describe form, chipped and
  broken edges. My planes are mostly flat fills plus faint hatching. The bristle / chalk passes at 0.15–0.35 opacity
  hardly show.
- **detail density:** hundreds of distinct architectural parts (cornices, shutters, chimneys, ironwork, signs). Mine
  has the essentials only.
- **edge control:** lost and found edges; mine are almost all hard mask edges.
- **colour richness inside the shadows:** reflected warm and cool light, not one tone per wall.

**Tools or painting?** Mostly **the painting**, made worse by **time and the replay cost**. The brushes can make
painterly marks (the brush sheet shows it), but I leaned on masks + fills because they are fast and safe, and with
67 s per look I could not afford the hundreds of small observed strokes a matte painting needs in 75 minutes. The real
tool gaps that held the look back: glows / haze that can't stack (gap 2), the replay cost (gap 1) and no perspective
plane helper (gap 9). With those fixed and about 3–4× the time, I think a much richer surface is in reach. Whether it
can reach Arcane's surface quality is not proven by this picture: **today, no.**

## Round 2 (member painter2): a surface / brushwork pass on the same document

**Pictures** (all in `C:\Users\Sam\.rostrum\waves\results\stage1\p-paint\`): `background-round2-step1.png` (after the
plaster pass), `background-round2-step2.png` (after water, stone, arch, sky, wall detail), final
`background-round2-1080p.png` (via `export`), and `background-round2-vs-reference.png` (via `ref`, beside
`arcane-80lv-2.jpg`).

**What I did.** Kept the design (one light, the arch as the focus, value groups, perspective) and painted over it in
7 new scripts, 16 new batches, each looked at before the next:
- `08_plaster.py`: 850 strokes on the 8 buildings on a new `plaster` layer: flat / bristle strokes that run along the
  wall planes toward the vanishing point, chalk rain streaks, broken `block` patches. Colours are picked off the wall
  layer and pushed warm near the glow, cool toward the roofs, dark and damp at the water. The windows, sills and
  cornices (strokes 58-225) were then **re-laid on top** from `stroke_info`, so the brushwork never buries them.
- `09_water_arch.py`: the hard-edged ellipse under the arch broken up: 260 wet drags along its rim (`wet=0.85,
  sample_all`), 520 dark ripples cutting into the light, 420 warm ripples on a `screen` layer that thin out past the
  old rim. (Its stone and arch-glow batches were undone, see misses; they are not in the document.)
- `10_stone_sky_detail.py`: bridge stone in a narrow value range, the canal seen through the arch painted along its
  planes, 240 broad bristle / flat strokes in the sky.
- `11_detail_rim.py`: shutters with louvres and lintel shadows beside all 36 near windows (positions **asked from the
  document**, not guessed), drainpipes with brackets and a lit edge, broken warm lines on corners facing the glow,
  chimney pots; the arch crown glow (screen dabs that lose the top of the arch into the light); 300 long dark / warm
  ripples across the lower rim of the reflection so it no longer reads as an oval.
- `12_bounce_edges.py`: warm light bounced up from the water onto the lower walls and cool sky light on the upper
  walls (360 screen bristle strokes, they stack), and 70 wet drags that lose the arch's inner edge, the tops of the
  far canal walls and the far rooflines.
- `13_windows_clouds.py`: the 17 lit windows (found by colour) get a hot off-centre core, a curtain, mullion and
  transoms; the thin cloud dashes get painted masses with warm undersides (278 strokes).
- `14_voussoirs_quay.py`: the arch ring as separate worn stones with dark joints and warm lower faces; quay top,
  quay face and boat painted along their planes with lamp-warmed colour and paving joints.

**Count and time.** About 4,920 new stroke ids (1556 → ~6480; the document is now 56 batches, ~6,480 ids). About 40
minutes of painting, of which roughly 13 minutes was waiting on runs and undos.

**Look-loop times now.** `see` / `small` / `values` / `export` / `what` / `landed`: **3-4 s** each, even at 6,000+
ops (round 1: ~67 s). Undo of the last 1-3 batches: ~10 s. A run costs its strokes: ~15-30 s for 300-800 dry strokes;
**wet strokes are the slow part** (09 took 3 min 21 s, mostly the 260 `wet + sample_all` drags; 12 took 84 s for 70).
Undoing a 4th batch in a row replays the whole document: that took **about 9 minutes** at ~6,000 ops (the single
worst cost of the session).

**`landed` on strokes that matter:** plaster 1556 (mean 0.39 px, 101 px clipped by its mask on purpose), rim drag
2574 (0.13 px), drainpipe 4576 (0.17 px), rim ripple 5009 (0.33 px), arch edge drag 5669 (0.00 px), arch stone 6102
(0.97 px), quay stroke 6195 (1.09 px): all landed. The new `landed` wording states both limits clearly (gap 4 of
round 1 is fixed).

**Misses (all planning, none placement):**
1. First bridge-stone pass sampled colours off the bridge layer, which already held voussoir and railing paint; the
   `block` strokes came out as greenish, glitchy rectangles. Undone; redone from the bridge tone in a narrow range.
2. First shutters were placed from my own guess of the window positions and landed beside nothing as teal stripes.
   Undone; redone from `stroke_info` of the real window strokes.
3. First arch-ring stones were too big, too varied in colour, and read as a ring of pebbles. Undone, made smaller,
   lower in opacity and colour drift. The two undos in a row past the kept states cost the 9-minute replay above.
4. Early ripples used a sine wobble on 8 points: they read as `~~~` squiggles, a pattern, in the upper water. Left
   in (they are lost under later strokes in most places), but visible on a close look.

**Remaining tool gaps.**
1. **Undo past the 3 kept states replays everything** (~9 min now). Needed: more kept states (or one every N
   batches), or undo of a named batch without a full replay.
2. **Wet strokes are slow** (~1.3 s each with `sample_all`). Lost edges and blending need hundreds of them.
3. **No "exclude" mask**: to paint plaster without burying windows I had to re-lay 168 window strokes on top. A mask
   made of "this mask minus those strokes" (or `mask_from_strokes`) would do it directly.
4. **No query for strokes by batch / colour / place**: I scanned id ranges with `stroke_info` in a loop. A
   `doc.strokes(batch=..., layer=...)` would be cleaner.
5. **No perspective plane helper** still (round 1 gap 9); every along-the-wall stroke needs my own vanishing-point maths.
6. **No colour sampling helper for scripts**: `layer_pixels` works, but "pick the seen colour at x, y" (composite
   at one point) would avoid sampling the wrong layer (miss 1).

**Honest judgement against the reference.** Better than round 1, still **not at the reference.** What moved: the
walls now have visible, plane-following brushwork and colour inside the shadows (warm bounce low, cool sky light
high); the bright reflection is a broken field of ripples instead of a hard ellipse; the arch ring reads as stones lit
from under the arch; near walls have shutters, pipes, chimneys; the clouds have mass. At thumbnail size the design is
unchanged (`values`: 60 / 28 / 10 / 2 %).
What is left: (a) **rendering of form and material**: Arcane's stones and plaster have planes, chips, stains and
lit/shadow sides on every block; mine has texture laid over flat shapes, so the buildings still read as boxes with a
painted skin. (b) **Edges**: the silhouettes (rooflines, bridge, far city, the far-canal trapezoids under the arch)
are still mostly the round-1 polygon edges; I lost only a few. (c) **The far city** and the view through the arch
are still flat cut-outs. (d) **Light design inside the forms**: the reference models light across each surface;
mine tints it.
**Tools or painting?** Mostly **painting and time**: every mark the reference has could be made with these brushes,
but it needs thousands of hand-judged strokes per building, form by form, not procedural scatter over a mask (which
is what I did to cover the frame in 40 minutes, and procedural scatter is exactly what keeps it looking like texture
on shapes). The tool costs that shape *how* an agent paints: slow wet strokes and the full replay on deep undo push
toward safe dry scatter; an exclude mask, a plane helper and stroke queries would make careful, observed painting
much cheaper. My estimate: reaching the reference needs ~4-6x this time spent on form-by-form rendering of the arch,
near walls and edges, with those tool fixes.
