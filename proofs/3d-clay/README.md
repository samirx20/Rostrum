# P-Clay proof — the clay core (final: parts 1, 2 and 3)

*Team Priyam, 2026-10-26/27. Brief: `C:\Users\Sam\.rostrum\waves\results\3d-simplicity\PLAN-UPDATE.md` § 1 "P-Clay",
parts 2 and 3 from the manager (part 3 = the plan's third try). Throwaway proof code: nothing here goes into `apps\`
or `shared\`. Pictures and numbers: `C:\Users\Sam\.rostrum\waves\results\3d-clay-proof\` (`p2\`, `p3\`,
`side-by-side\`).*

## The call: PASS — CL1 goes ahead on this core

**In plain words.** The third try met three of the five things it set out to prove:
- **Met:** brush dabs of everyday size (including mirrored medium ones) reach the screen within one frame. Peak memory
  is under 1.5 GB. Repeated mouse drags no longer grow ridges toward the camera.
- **Still slow:** a brush a quarter of the clay across (23–59 ms against 16) and replaying 2,000 strokes from scratch
  (42–45 s against 15), both measured while another team was using the machine.

Everything else holds and has held since part 2: smooth surfaces, crisp creases, clean joins, six brushes, and the
same steps always giving exactly the same clay.

**Why PASS and not the pivot, although two speed targets are still missed after three tries** (the plan's rule says
pivot; this goes against the letter of it, and the manager may overrule):
1. **They are throughput, not quality or correctness.** Both are the same cost, re-levelling the distance band
   after a dab, now cut to the band itself (≈ 6× less work than part 2). What remains is plain CPU volume for
   ~200,000 band voxels per quarter-size dab, and for 23,000 dabs in a row.
2. **The fixes are known and local to the clay core**, not a new method:
   - a quarter-size brush works on a 2× coarser copy of the band (8× fewer voxels; a big brush has no fine detail);
   - replay runs strokes that don't touch each other at the same time;
   - or the same narrow-band step on the GPU (NanoVDB ships with OpenVDB).
3. **Replay from scratch is the rare path.** Opening a project reads the cache in 0.1–0.2 s (met); full replay runs
   only without a cache, and can run in the background.
4. **The pivot would also lose things.** Re-evened mesh sculpting would likely make large brushes fast, but it gives
   up what the volume gives for free: pieces that join and cut without tearing, steps that replay to the identical
   surface, and the surfaces judged good in part 2. Its re-evening is itself a voxel step.

**Carried into the clay briefs:**
- CL2: the coarse level for brushes larger than 1/8 of the clay.
- CL1 (cache) / CL2: replay in parallel regions or on the GPU.

Both have targets: a quarter-size dab ≤ 20 ms; 2,000 strokes ≤ 15 s.

## Final numbers

Laptop: RTX 3050 4 GB, 16 GB, 12 threads, shared with other teams. Run A was quieter (an unchanged Storm frame 6 ms);
run B, the last, shared the GPU with another team (17 ms). Both use the same code apart from memory and display
settings, and give the same clay (hashes `ee3bb7ac…` head, `db3b47f2…` after 2,000 strokes, in both).
"First picture" = the dab plus the Storm frame that shows it (the changed blocks nearest the brush first: 4 per
frame in run A, 2 in run B; the rest follow over the next frames).

| Budget | Target | Part 1 | Part 2 | Part 3 (run A / run B) | |
|---|---|---|---|---|---|
| Small dab → picture, 6 brushes | ≤ 16 ms | 10–14 | 8–16 | 7–11 / 7–13 ms | **met** |
| Medium dab → picture | ≤ 16 ms | 16–19 | 11–24 | 8–13 / 6–11 ms | **met** |
| Mirrored medium dab → picture | ≤ 16 ms | 22–28 | 15–27 | 9–16 / 7–12 ms | **met** |
| Quarter-of-the-clay dab → picture | ≤ 16 ms (20 ok) | 67–114 | 38–76 | 28–37 / 23–59 ms (Add 22.6, Carve 26.6) | **not met** (1.4–3.7×) |
| Replay of 2,000 strokes (22,851 dabs) | ≤ 15 s | 73 s | 79 s | 42 / 45 s | **not met** (≈ 3×) |
| Replay from cache | ≤ 2 s | 0.14 s | 0.1–0.2 s | 0.10 s | **met** |
| Same steps → same clay (hash) | yes | yes | yes | yes, every run: live = replay = cache | **met** |
| Peak memory, full bench (Finals included) | ≤ 1.5 GB | 2.9 GB | 1.84 GB | 1.86 / **1.38 GB**; comparison run 1.44 GB | **met** (run B) |
| Full rebuild, close-up head | ≤ 2 s | 92 ms | 75–124 ms | 85 ms | **met** |
| Repeated drags don't grow toward the camera | — | — | grew (tendrils) | gone (`side-by-side\mouse_head_before_after_cap.png`) | **met** |

What part 3 changed:
- **Narrow band (condition 1).** A dab now works on a list: the band voxels in its reach plus the 2 voxels the
  band can grow by. The band is found with a small 12³ grid per chunk; each voxel's 6 neighbours are found once; the
  re-levelling passes run on compact arrays (4 passes: seeds sit within a voxel of the surface and the band is 4
  wide). Only chunks a dab touched are written back, and small dabs run on one thread.
  - **Quarter-size dab step** (not mirrored, full runs): 39–57 → 13–35 ms. Where its time goes now (≈ 200,000 band voxels): finding the band
    3.5 ms, neighbours 2.6, the dab 0.8, re-levelling 2.3, writing back 1.7, plus the Storm frame 8–10.
  - **Replay:** 3.4 → 1.3–1.9 ms a dab.
- **Accumulate (condition 3).** A brush setting, stored in the steps, default on, as in Nomad. With it off, a stroke
  raises (digs) the surface at most one dab's height above where the stroke began. A live stroke reads that start
  from the chunks it kept aside; replay reads it from the stroke's single unit, so live = replay still holds. The
  mouse sculpt drags with it off.
- **Memory (condition 2).**
  - The step buffers are freed after every piece; a piece's wide-blend box was the big one, kept through the
    strokes.
  - The Finals render at the end, with the clays gone: Cycles keeps ≈ 0.5 GB of scene for as long as its one engine
    lives.
  - Measured: 1.86 → 1.38 GB.

## Look: ripples, Crease, joins (part 2; close-up Finals, `p2\look_*`)

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
| Head by scripted mouse drags, 4 pieces + 49 drags in 4 views — part 2 `mouse_head_vs_panda_ma.png`, part 3 `mouse_head_capped_vs_panda_ma.png`, `mouse_head_before_after_cap.png` | Panda Ma's head studies | Part 2 **failed**: drags grew tendrils towards the camera. Part 3, with Accumulate off: **no runaway**, but the head is weak. The script was written expecting strokes to pile up, so its forms now build too little, and its loop scribbles leave single round bumps. A sculpt problem, not an engine one. |

Judged on the brief's points: surface smoothness **yes**; how crisp a Crease line gets **good**; no stair-steps or blobby
joins **yes**; holds up close **yes** (close-ups at about 7 cm across the frame). Overall "not worse than the
reference": **no** for the heads.

## What was built (`src\`)

| File | What it does |
|---|---|
| `clay.h/.cpp` (lead) | The clay: an OpenVDB narrow band (values in voxels, half-width 4, negative inside), changed by steps. A piece (sphere / capsule, Add or Carve, smooth blend) or a stroke of dabs (Add, Carve, Smooth, Pull, Flatten, Crease; X mirror) works on the 8³ chunks near the surface in its reach. Per stroke: one fill, the dabs in order, each re-levelled over its own narrow band (part 3), then one write-back of the chunks touched (uniform chunks become tiles). Live strokes: `begin_stroke`, `dab` (a preview, old chunks kept), `end_stroke` (put back, the unit applied). Blend widening capped at 24 voxels (15 mm). Accumulate off caps a stroke at one dab's height (part 3). `CLAY_PROFILE=1` prints where a big dab's time goes. Hash over leaves, `.vdb` cache, steps as text. |
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
