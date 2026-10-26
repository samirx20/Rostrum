# P-Clay proof — the clay core (final, parts 1 + 2)

*Team Priyam, 2026-10-26/27. Brief: `C:\Users\Sam\.rostrum\waves\results\3d-simplicity\PLAN-UPDATE.md` § 1 "P-Clay",
part 2 brief from the manager. Throwaway proof code: nothing here goes into `apps\` or `shared\`. Pictures and numbers:
`C:\Users\Sam\.rostrum\waves\results\3d-clay-proof\` (part 2 in `p2\`, side-by-sides in `side-by-side\`).*

## Verdict: PASS WITH CONDITIONS

**In plain words.** Clay on a sparse volume works and looks right. Surfaces are smooth (the part-1 ripples are gone,
cause found), a Crease line is crisp, joins between pieces are clean fillets, and the six brushes (Add, Carve,
Smooth, Pull, Flatten, Crease) work. The same steps always give exactly the same clay, live, replayed or loaded. The
everyday brush sizes reach the screen in about one frame. **Three budgets are still missed, by a lot**: a brush a
quarter of the clay across (≈ 40–75 ms, target 16), replaying 2,000 strokes (≈ 79 s, target 15) and peak memory
(1.4–1.8 GB, target 1.5). All three trace to one measured cost: re-levelling the distance band after each dab is
about 17 ms of CPU work per dab. Next to Nomad Sculpt pieces, our sculpts are clearly weaker. That is the sculpting
(a script placing shapes blind, and one missing brush control), not the clay surface.

**Why not FAIL / pivot.** Strictly by the brief's rule ("all budgets met, or within 25 % with a clear fix") this is not
a pass: three budgets are 1.2–5× over. I still recommend going on with clay, not pivoting to re-evened mesh
sculpting, because what fails is one engine cost, measured and local, not the method:
- surface quality, determinism and the brushes all pass;
- small and medium dabs are at or near budget;
- the failing paths share one hot loop.

**The conditions** (put into CL1 / CL2; if they don't hold after CL1's first package, that is the third try, and
the pivot applies):
1. **Re-level only next to the voxels a dab changed** (today the whole dab region, 5 passes: 85 % of the time), or
   move the step to the GPU. Targets: large dab ≤ 16 ms, replay of 2,000 strokes ≤ 15 s.
2. **Peak memory ≤ 1.5 GB in the app**: one clay alive, Cycles scene released between Finals, scratch capped.
3. **A stroke's build-up is capped** (Nomad's "accumulate" off / brush plane): without it, repeated mouse drags grow
   ridges towards the camera (the mouse head below).

## Numbers

Laptop: RTX 3050 4 GB, 16 GB, 12 threads, shared with other teams. Wall times swing run to run, so two runs are shown.
The **quick** run (`p2\` quick bench, 300 strokes, no Finals) and the **full** run (`p2\bench\numbers_bench.json`,
2,000 strokes, Finals) came on a quieter and a busier machine. Clay: part 1's head, voxel 0.000625, 3.3 M active
voxels, 1.25 M triangles. "First picture" is a dab plus the Storm frame that shows it: Storm gets the 8 changed blocks
nearest the brush per frame, and the rest follow over the next frames. "Stroke end" (re-applying the stroke as one
unit) and the frames until every block is shown are in the JSON.

| Budget | Target | Part 1 | Part 2 (quick / full run) | |
|---|---|---|---|---|
| Dab → picture, small (r 6 voxels), all 6 brushes | ≤ 16 ms | 10–14 ms | 8–15 / 12–16 ms | **met** |
| Dab → picture, medium (r 19 voxels) | ≤ 16 ms | 16–19 ms | 11–18 / 11–24 ms (Crease, Pull fastest; Add, Carve slowest) | within 25 % on the quiet run; over on the busy one |
| Mirrored medium | ≤ 16 ms | 22–28 ms | 16.5–22.7 / 15–27 ms | Pull, Crease, Smooth met; Add, Carve, Flatten over |
| Dab → picture, quarter of the clay (r 66 voxels) | ≤ 16 ms | 67–114 ms | 38–42 / 52–76 ms; mirrored 63–112 ms | **over** (Storm is 10–17 ms of it; the step 25–90 ms) |
| Full rebuild, close-up head | ≤ 2 s | 92 ms | 75–124 ms | **met** |
| Replay of 2,000 strokes (22,852 dabs) | ≤ 15 s | 73 s | 79 s (2.8–3.4 ms a dab; 17.5 ms a dab on one thread) | **over** |
| Replay from cache | ≤ 2 s | 0.14 s | 0.10–0.19 s | **met** |
| Same steps → same hash | yes | yes | yes: head live = replay, 2,000 strokes live = replay = cache, in every run | **met** |
| Memory, process peak | ≤ 1.5 GB | 2.9 GB | 1.4 GB (quick, compare runs) / 1.84 GB (full: bench + 2,000 strokes + kept Cycles scene + Finals); clay grid 34–40 MB | **over** in the full run |
| Storm frame, nothing changed | — | 6.9 ms | 7.0 ms | |

What part 2 changed for speed and memory:
- **A stroke is one unit.** Live: each dab is shown at once, then at mouse-up the clay is put back and the stroke is
  applied in one pass. Replay applies the same pass, so live and replay are bit-identical.
- **Chunk-major buffers, allocated without clearing**, shared by all clays: memory only for the chunks a step touches.
- **A single dab no longer widens the band** (part 2's first try did, and a large dab went to 100 ms).
- **Storm's block budget per frame.**
- **The studio lights reach Storm as simple lights.** As scene lights they made a frame 20 ms.
- Replay went from 73 to 79 s, i.e. no gain. A stroke shares its fill and write-back, but each dab still re-levels its
  whole region. A single-thread run shows that is real work, not thread overhead: condition 1.

## Look: ripples, Crease, joins (close-up Finals, `p2\look_*`)

- **Ripples: cause found and fixed.** Part 1's faint stair-steps on the cheeks came from the distance values, not from
  the voxel size or the normals. After each dab, the voxels next to the surface were re-seeded from where the surface
  crossed their edges (1/d² = Σ 1/d_axis²). That formula is exact only for flat surfaces and leaves voxel-scale noise,
  which smooth normals then show as rings. Re-seeding by the value's own gradient (v / |∇v|, central differences)
  removes it. A sphere after 4 overlapping Smooth strokes (`look_sphere_smoothed_final.png`) is clean. An A/B with and
  without the new vertex projection in the mesher (`p2\noproject\`) shows no visible difference, so the field was the
  cause.
- **Crease** (`look_brushes_final.png`): two lines on a sphere read as crisp grooves with lit rims. Faint beading
  inside the groove where dabs overlap; a finer dab spacing for Crease (CL2) removes it.
- **Joins** (`look_join_final.png`): an arm blended into a body and smoothed along the join: one even fillet, no lump,
  no stair-step.
- Flatten and Pull work (same picture); the small character uses Crease ×18 and Flatten, Pull.

## The comparison (`side-by-side\`, references private in `C:\Users\Sam\.rostrum\references\3d\`)

References: 7 pictures their artists posted publicly on the Nomad Sculpt forum (`sources.md` there). No ZBrush
pictures: those pages need a browser.

| Ours | Reference | Judgement |
|---|---|---|
| Agent's head, 518 steps (53 pieces, 30 strokes) — `agent_head_vs_georges_bust.png`, `agent_head_front_vs_brandt_peters.png` | Georges' portrait bust; Brandt Peters' stylised bust | **Far below.** The surface is smooth and the lit edges are clean, but the forms are blocky (brow shelf, jaw step, tube collarbones) and there are no secondary forms or hair. A script placing shapes it can't see is the limit. CL7's look tools are the answer (an agent that looks at its frame). |
| Agent's small character, 633 steps — `agent_character_vs_help_help_chibi.png` | help_help's chibi (painted) | **Closest.** The finish (clean joins, crisp smile, belt, collar and knee lines) is at a toy-figure level. The forms are simpler and the brows lumpy. Not worse in surface quality; worse in design. |
| Head by scripted mouse drags, 4 pieces + 49 drags in 4 views — `mouse_head_vs_panda_ma.png` | Panda Ma's head studies | **Fails.** Repeated drags grow ridges and tendrils towards the camera: each dab is cast onto the bump the previous one raised, and a stroke's build-up isn't capped. Condition 3. |

Judged on the brief's points: surface smoothness **yes**; how crisp a Crease line gets **good**; no stair-steps or blobby
joins **yes**; holds up close **yes** (close-ups at about 7 cm across the frame). Overall "not worse than the
reference": **no** for the heads.

## What was built (`src\`)

| File | What it does |
|---|---|
| `clay.h/.cpp` (lead) | The clay: an OpenVDB narrow band (values in voxels, half-width 4, negative inside), changed by steps. A piece (sphere / capsule, Add or Carve, smooth blend) or a stroke of dabs (Add, Carve, Smooth, Pull, Flatten, Crease; X mirror) works on the 8³ chunks near the surface in its reach. Per stroke: one fill, the dabs in order, each re-levelled over its own chunks, then one write-back (uniform chunks become tiles). Live strokes: `begin_stroke`, `dab` (a preview, old chunks kept), `end_stroke` (put back, the unit applied). Blend widening capped at 24 voxels (15 mm). Hash over leaves, `.vdb` cache, steps as text. |
| `session.h` (lead) | Sculpting session: world-space strokes (an agent), pixel-path strokes through a camera (a mouse), replay by stroke units. |
| `mesh.h/.cpp` (member; lead added smooth normals and vertex projection) | Surface nets per 32³ block, crack-free, continuous normals, vertices projected onto the cell's zero surface. |
| `view.h/.cpp` (members) | Storm: one prim per block, only changed blocks sent. Cycles: one engine for the View's life (a second one crashed in part 1), the studio look (dark gradient background, key / fill / rim panels, low dome). |
| `sculpts.cpp` (member) | The comparison sculpts: agent head, agent small character, mouse head; their cameras. |
| `compose.py` (member) | Side-by-side sheets: `python -I compose.py ours.png ref.jpg out.png [--label-left …] [--label-right …]`. |
| `main.cpp` (lead) | Modes: `bench` (the numbers), `look` (close-ups), `compare` (the sculpts + Finals), `check` (every head step's surface has no hole; edges shared by 4 = two sheets touching, not counted), `replay <file>` (pieces and dabs timed apart; `CLAY_THREADS=n`). |

Build and run (both through `heavy.ps1`): `build.bat` (`CLAY_CMAKE_ARGS=-DCLAY_SCULPTS=OFF` without the sculpts), then
`run.bat <out folder> bench|look|compare|check|replay …`. Storm uses the scene lights with `CLAY_STORM_SCENE=1`.

## Found and fixed on the way (worth knowing for CL1)

- Draw on the RTX: export `NvOptimusEnablement` / `AmdPowerXpressRequestHighPerformance` (Storm was on the AMD chip: 40 → 7 ms).
- Nested TBB loops with thread-local buffers left holes at block seams, different every run (part 1). Block listing
  must include the block below each leaf on each axis.
- Re-levelling swaps buffers. Inside a stroke only the dab's chunks are current in the other buffer, so copy back.
  Getting this wrong grew false surfaces (3× the voxels) and broke the hash.
- Seeding by edge crossings leaves voxel-scale ripples; seed by v / |∇v|.
- A second Cycles engine after the first is destroyed crashes; keep one.
- PowerShell variables ignore case (`$R` = `$r`), which bit the run scripts once.

## Libraries

- **OpenVDB 13.0.0** (MPL-2.0). The DLL is already in the 3D library folder (`runtime\bin\openvdb.dll`). The headers and
  import library come from the same Blender `lib-windows_x64` bundle (v5.2.2, 60d6e96; that DLL is byte-identical), in
  `C:\Users\Sam\.rostrum\downloads\blender-lib-v5.2.2-openvdb\` (80 MB with its Git data). Its own dependencies (oneTBB
  Apache-2.0, Blosc BSD-3-Clause, zlib, Imath BSD-3-Clause) are inside the DLL and already listed for the Cycles bundle.
  For CL1, `apps\3d\libs\lay_out.py` should copy `openvdb\include` and `openvdb.lib` into the sdk.
- Pillow (already in the shared venv) for `compose.py`, dev only.
- No new downloads in part 2 except the private reference pictures (not shipped, not in the repo).

## Attribution rows

| Name | Version | Licence | Used by | How it's linked | Ships? | What it asks of us | Source |
|---|---|---|---|---|---|---|---|
| OpenVDB (headers + import library; DLL already listed) | 13.0.0 (Blender lib-windows_x64 v5.2.2, 60d6e96) | MPL-2.0 | `proofs/3d-clay` (the clay volume); later `apps/3d/core` | dynamic | dev only (proof); the DLL already ships with the 3D libraries | Keep the notice; changes to OpenVDB's own files stay MPL (none made) | https://github.com/AcademySoftwareFoundation/openvdb |
| Pillow | 13 (shared venv) | MIT-CMU (HPND) | `proofs/3d-clay/compose.py` | Python package | dev only | Keep the notice | https://pypi.org/project/pillow/ |
